"""Orchestrator coordinating the deep research workflow.

Rewritten to use LangChain + asyncio instead of hello-agents.
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator

from langchain_openai import ChatOpenAI

from agent_core import SimpleAgent
from config import Configuration
from models import SummaryState, SummaryStateOutput, TodoItem
from note_tools import NoteTool
from prompts import (
    report_writer_instructions,
    task_summarizer_instructions,
    todo_planner_system_prompt,
)
from services.planner import PlanningService
from services.reporter import ReportingService
from services.search import dispatch_search, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


class DeepResearchAgent:
    """Coordinator orchestrating TODO-based research workflow using LangChain + asyncio."""

    def __init__(self, config: Configuration | None = None) -> None:
        self.config = config or Configuration.from_env()
        self.llm = self._init_llm()

        # Note tool
        self.note_tool = (
            NoteTool(workspace=self.config.notes_workspace)
            if self.config.enable_notes
            else None
        )

        # Build tools dict for SimpleAgent
        tools: dict[str, Callable] = {}
        if self.note_tool:
            tools["note"] = self.note_tool.run

        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self._tool_event_sink_enabled = False

        # Create agents
        self.todo_agent = self._create_agent(
            name="研究规划专家",
            system_prompt=todo_planner_system_prompt.strip(),
            tools=tools,
        )
        self.report_agent = self._create_agent(
            name="报告撰写专家",
            system_prompt=report_writer_instructions.strip(),
            tools=tools,
        )

        self._summarizer_factory: Callable[[], SimpleAgent] = lambda: self._create_agent(
            name="任务总结专家",
            system_prompt=task_summarizer_instructions.strip(),
            tools=tools,
        )

        self.planner = PlanningService(self.todo_agent, self.config)
        self.summarizer = SummarizationService(self._summarizer_factory, self.config)
        self.reporting = ReportingService(self.report_agent, self.config)
        self._last_search_notices: list[str] = []

    # ------------------------------------------------------------------
    # LLM factory
    # ------------------------------------------------------------------

    def _init_llm(self) -> ChatOpenAI:
        """Create ChatOpenAI instance matching configuration."""
        llm_kwargs: dict[str, Any] = {"temperature": 0.0}

        model_id = self.config.llm_model_id or self.config.local_llm
        if model_id:
            llm_kwargs["model_name"] = model_id

        provider = (self.config.llm_provider or "").strip()

        if provider == "ollama":
            llm_kwargs["openai_api_base"] = self.config.sanitized_ollama_url()
            llm_kwargs["openai_api_key"] = self.config.llm_api_key or "ollama"
        elif provider == "lmstudio":
            llm_kwargs["openai_api_base"] = self.config.lmstudio_base_url
            if self.config.llm_api_key:
                llm_kwargs["openai_api_key"] = self.config.llm_api_key
        else:
            if self.config.llm_base_url:
                llm_kwargs["openai_api_base"] = self.config.llm_base_url
            if self.config.llm_api_key:
                llm_kwargs["openai_api_key"] = self.config.llm_api_key

        return ChatOpenAI(**llm_kwargs)

    def _create_agent(
        self,
        *,
        name: str,
        system_prompt: str,
        tools: dict[str, Callable] | None = None,
    ) -> SimpleAgent:
        """Create a SimpleAgent sharing tool tracker."""
        return SimpleAgent(
            name=name,
            llm=self.llm,
            system_prompt=system_prompt,
            tools=tools or {},
            tool_call_listener=self._tool_tracker.record,
        )

    # ------------------------------------------------------------------
    # Tool event sink
    # ------------------------------------------------------------------

    def _set_tool_event_sink(self, sink: Callable[[dict[str, Any]], None] | None) -> None:
        self._tool_event_sink_enabled = sink is not None
        self._tool_tracker.set_event_sink(sink)

    # ------------------------------------------------------------------
    # Sync API (for /research endpoint)
    # ------------------------------------------------------------------

    def run(self, topic: str) -> SummaryStateOutput:
        """Execute the research workflow synchronously."""
        state = SummaryState(research_topic=topic)
        state.todo_items = self.planner.plan_todo_list(state)
        self._drain_tool_events(state)

        if not state.todo_items:
            logger.info("No TODO items generated; falling back to single task")
            state.todo_items = [self.planner.create_fallback_task(state)]

        for task in state.todo_items:
            # _execute_task is a generator — must consume it
            for _ in self._execute_task(state, task, emit_stream=False):
                pass

        report = self.reporting.generate_report(state)
        self._drain_tool_events(state)
        state.structured_report = report
        state.running_summary = report
        self._persist_final_report(state, report)

        return SummaryStateOutput(
            running_summary=report,
            report_markdown=report,
            todo_items=state.todo_items,
        )

    # ------------------------------------------------------------------
    # Async streaming API (for /research/stream endpoint)
    # ------------------------------------------------------------------

    async def run_stream(self, topic: str) -> AsyncIterator[dict[str, Any]]:
        """Execute workflow yielding incremental progress events (async)."""
        state = SummaryState(research_topic=topic)
        logger.debug("Starting streaming research: topic=%s", topic)
        yield {"type": "status", "message": "初始化研究流程"}

        state.todo_items = self.planner.plan_todo_list(state)
        for event in self._drain_tool_events(state, step=0):
            yield event
        if not state.todo_items:
            state.todo_items = [self.planner.create_fallback_task(state)]

        channel_map: dict[int, dict[str, Any]] = {}
        for index, task in enumerate(state.todo_items, start=1):
            token = f"task_{task.id}"
            task.stream_token = token
            channel_map[task.id] = {"step": index, "token": token}

        yield {
            "type": "todo_list",
            "tasks": [self._serialize_task(t) for t in state.todo_items],
            "step": 0,
        }

        event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        _loop = asyncio.get_running_loop()

        async def _queue_put(item: dict[str, Any]) -> None:
            await event_queue.put(item)

        def _threadsafe_put(payload: dict[str, Any]) -> None:
            """Put an event on the queue — safe from any thread."""
            asyncio.run_coroutine_threadsafe(event_queue.put(payload), _loop)

        def enqueue(
            event: dict[str, Any],
            *,
            task: TodoItem | None = None,
            step_override: int | None = None,
        ) -> None:
            payload = dict(event)
            target_task_id = payload.get("task_id")
            if task is not None:
                target_task_id = task.id
                payload["task_id"] = task.id

            channel = channel_map.get(target_task_id) if target_task_id is not None else None
            if channel:
                payload.setdefault("step", channel["step"])
                payload["stream_token"] = channel["token"]
            if step_override is not None:
                payload["step"] = step_override
            _threadsafe_put(payload)

        def tool_event_sink(event: dict[str, Any]) -> None:
            enqueue(event)

        self._set_tool_event_sink(tool_event_sink)

        async def worker(task: TodoItem, step: int) -> None:
            try:
                enqueue({
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "in_progress",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                }, task=task)

                async for event in self._execute_task_async(state, task, step=step):
                    enqueue(event, task=task)
            except Exception as exc:
                logger.exception("Task execution failed", exc_info=exc)
                enqueue({
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "failed",
                    "detail": str(exc),
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                }, task=task)
            finally:
                _threadsafe_put({"type": "__task_done__", "task_id": task.id})

        tasks_coros = [
            worker(task, channel_map.get(task.id, {}).get("step", 0))
            for task in state.todo_items
        ]
        worker_tasks = [asyncio.create_task(c) for c in tasks_coros]

        active_workers = len(state.todo_items)
        finished_workers = 0

        try:
            while finished_workers < active_workers:
                event = await event_queue.get()
                if event.get("type") == "__task_done__":
                    finished_workers += 1
                    continue
                yield event

            # Drain remaining events
            while not event_queue.empty():
                try:
                    event = event_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if event.get("type") != "__task_done__":
                    yield event
        finally:
            self._set_tool_event_sink(None)
            for t in worker_tasks:
                if not t.done():
                    t.cancel()
            await asyncio.gather(*worker_tasks, return_exceptions=True)

        # Generate final report
        report = await asyncio.to_thread(self.reporting.generate_report, state)
        final_step = len(state.todo_items) + 1
        for event in self._drain_tool_events(state, step=final_step):
            yield event
        state.structured_report = report
        state.running_summary = report

        note_event = self._persist_final_report(state, report)
        if note_event:
            yield note_event

        yield {
            "type": "final_report",
            "report": report,
            "note_id": state.report_note_id,
            "note_path": state.report_note_path,
        }
        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Task execution (sync + async)
    # ------------------------------------------------------------------

    def _execute_task(
        self,
        state: SummaryState,
        task: TodoItem,
        *,
        emit_stream: bool,
        step: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run search + summarization for a single task (sync)."""
        task.status = "in_progress"

        search_result, notices, answer_text, backend = dispatch_search(
            task.query, self.config, state.research_loop_count,
        )
        self._last_search_notices = notices
        task.notices = notices

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
        else:
            self._drain_tool_events(state)

        if notices and emit_stream:
            for notice in notices:
                if notice:
                    yield {
                        "type": "status", "message": notice,
                        "task_id": task.id, "step": step,
                    }

        if not search_result or not search_result.get("results"):
            task.status = "skipped"
            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "task_status", "task_id": task.id, "status": "skipped",
                    "title": task.title, "intent": task.intent,
                    "note_id": task.note_id, "note_path": task.note_path, "step": step,
                }
            else:
                self._drain_tool_events(state)
            return
        elif not emit_stream:
            self._drain_tool_events(state)

        sources_summary, context = prepare_research_context(
            search_result, answer_text, self.config,
        )
        task.sources_summary = sources_summary

        state.web_research_results.append(context)
        state.sources_gathered.append(sources_summary)
        state.research_loop_count += 1

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "sources", "task_id": task.id,
                "latest_sources": sources_summary, "raw_context": context,
                "step": step, "backend": backend,
                "note_id": task.note_id, "note_path": task.note_path,
            }

            summary_stream, summary_getter = self.summarizer.stream_task_summary(
                state, task, context,
            )
            try:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                for chunk in summary_stream:
                    if chunk:
                        yield {
                            "type": "task_summary_chunk", "task_id": task.id,
                            "content": chunk, "note_id": task.note_id, "step": step,
                        }
                    for event in self._drain_tool_events(state, step=step):
                        yield event
            finally:
                summary_text = summary_getter()
        else:
            summary_text = self.summarizer.summarize_task(state, task, context)
            self._drain_tool_events(state)

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status", "task_id": task.id, "status": "completed",
                "summary": task.summary, "sources_summary": task.sources_summary,
                "note_id": task.note_id, "note_path": task.note_path, "step": step,
            }
        else:
            self._drain_tool_events(state)

    async def _execute_task_async(
        self,
        state: SummaryState,
        task: TodoItem,
        *,
        step: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run search + summarization for a single task (async)."""
        task.status = "in_progress"

        # Search is blocking — run in thread
        search_result, notices, answer_text, backend = await asyncio.to_thread(
            dispatch_search, task.query, self.config, state.research_loop_count,
        )
        self._last_search_notices = notices
        task.notices = notices

        for event in self._drain_tool_events(state, step=step):
            yield event

        if notices:
            for notice in notices:
                if notice:
                    yield {
                        "type": "status", "message": notice,
                        "task_id": task.id, "step": step,
                    }

        if not search_result or not search_result.get("results"):
            task.status = "skipped"
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status", "task_id": task.id, "status": "skipped",
                "title": task.title, "intent": task.intent,
                "note_id": task.note_id, "note_path": task.note_path, "step": step,
            }
            return

        sources_summary, context = prepare_research_context(
            search_result, answer_text, self.config,
        )
        task.sources_summary = sources_summary

        state.web_research_results.append(context)
        state.sources_gathered.append(sources_summary)
        state.research_loop_count += 1

        for event in self._drain_tool_events(state, step=step):
            yield event
        yield {
            "type": "sources", "task_id": task.id,
            "latest_sources": sources_summary, "raw_context": context,
            "step": step, "backend": backend,
            "note_id": task.note_id, "note_path": task.note_path,
        }

        # Summarize (sync streaming, so run in thread)
        def _run_summarizer():
            stream, getter = self.summarizer.stream_task_summary(state, task, context)
            chunks = list(stream)
            return chunks, getter()

        # Actually, streaming from thread is tricky. Use the sync version instead.
        summary_text = await asyncio.to_thread(
            self.summarizer.summarize_task, state, task, context,
        )

        for event in self._drain_tool_events(state, step=step):
            yield event

        task.summary = summary_text.strip() if summary_text else "暂无可用信息"
        task.status = "completed"

        for event in self._drain_tool_events(state, step=step):
            yield event
        yield {
            "type": "task_status", "task_id": task.id, "status": "completed",
            "summary": task.summary, "sources_summary": task.sources_summary,
            "note_id": task.note_id, "note_path": task.note_path, "step": step,
        }

    # ------------------------------------------------------------------
    # Tool events
    # ------------------------------------------------------------------

    def _drain_tool_events(
        self, state: SummaryState, *, step: int | None = None,
    ) -> list[dict[str, Any]]:
        events = self._tool_tracker.drain(state, step=step)
        if self._tool_event_sink_enabled:
            return []
        return events

    # ------------------------------------------------------------------
    # Serialization & helpers
    # ------------------------------------------------------------------

    def _serialize_task(self, task: TodoItem) -> dict[str, Any]:
        return {
            "id": task.id, "title": task.title, "intent": task.intent,
            "query": task.query, "status": task.status, "summary": task.summary,
            "sources_summary": task.sources_summary,
            "note_id": task.note_id, "note_path": task.note_path,
            "stream_token": task.stream_token,
        }

    def _persist_final_report(self, state: SummaryState, report: str) -> dict[str, Any] | None:
        if not self.note_tool or not report or not report.strip():
            return None

        note_title = f"研究报告：{state.research_topic}".strip() or "研究报告"
        tags = ["deep_research", "report"]
        content = report.strip()

        note_id = self._find_existing_report_note_id(state)
        if note_id:
            response = self.note_tool.run({
                "action": "update", "note_id": note_id, "title": note_title,
                "note_type": "conclusion", "tags": tags, "content": content,
            })
            if response.startswith("❌"):
                note_id = None

        if not note_id:
            response = self.note_tool.run({
                "action": "create", "title": note_title,
                "note_type": "conclusion", "tags": tags, "content": content,
            })
            note_id = self._extract_note_id_from_text(response)

        if not note_id:
            return None

        state.report_note_id = note_id
        if self.config.notes_workspace:
            note_path = Path(self.config.notes_workspace) / f"{note_id}.md"
            state.report_note_path = str(note_path)

        payload: dict[str, Any] = {
            "type": "report_note", "note_id": note_id,
            "title": note_title, "content": content,
        }
        if self.config.notes_workspace:
            payload["note_path"] = str(Path(self.config.notes_workspace) / f"{note_id}.md")

        return payload

    def _find_existing_report_note_id(self, state: SummaryState) -> str | None:
        if state.report_note_id:
            return state.report_note_id

        for event in reversed(self._tool_tracker.as_dicts()):
            if event.get("tool") != "note":
                continue
            parameters = event.get("parsed_parameters") or {}
            if not isinstance(parameters, dict):
                continue
            action = parameters.get("action")
            if action not in {"create", "update"}:
                continue
            note_type = parameters.get("note_type")
            if note_type != "conclusion":
                title = parameters.get("title")
                if not (isinstance(title, str) and title.startswith("研究报告")):
                    continue
            note_id = parameters.get("note_id")
            if not note_id:
                note_id = self._tool_tracker._extract_note_id(event.get("result", ""))
            if note_id:
                return note_id

        return None

    @staticmethod
    def _extract_note_id_from_text(response: str) -> str | None:
        if not response:
            return None
        match = re.search(r"ID:\s*([^\n]+)", response)
        if match:
            return match.group(1).strip()
        return None


def run_deep_research(topic: str, config: Configuration | None = None) -> SummaryStateOutput:
    """Convenience function mirroring the class-based API."""
    agent = DeepResearchAgent(config=config)
    return agent.run(topic)
