"""LangGraph StateGraph orchestrator — replaces manual DeepResearchAgent orchestration.

Uses a proper state graph with conditional edges for the research loop:
  plan → search → summarize → [continue?] → search ... → report
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from langgraph.graph import END, StateGraph

from config import Configuration
from models import TodoItem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Orchestrator state
# ---------------------------------------------------------------------------


@dataclass
class ResearchGraphState:
    """State carried through the LangGraph research workflow."""

    # Input
    research_topic: str = ""
    search_api: str = ""
    max_loops: int = 3

    # Planning output
    todo_items: list[dict[str, Any]] = field(default_factory=list)

    # Loop tracking
    current_task_index: int = 0
    research_loop_count: int = 0

    # Accumulated results
    web_research_results: list[str] = field(default_factory=list)
    sources_gathered: list[str] = field(default_factory=list)

    # Task summaries
    task_summaries: dict[int, str] = field(default_factory=dict)
    task_sources: dict[int, str] = field(default_factory=dict)

    # Final output
    report_markdown: str = ""
    running_summary: str = ""
    report_note_id: str = ""
    report_note_path: str = ""

    # Control
    error: str = ""
    status: str = "pending"


# ---------------------------------------------------------------------------
# Node implementations (injected via callables)
# ---------------------------------------------------------------------------


class ResearchOrchestrator:
    """LangGraph-based orchestrator for deep research workflows.

    Each node is a callable that receives state and returns updated state dict.
    The graph is compiled once and can be re-used for multiple runs.
    """

    def __init__(
        self,
        *,
        plan_node: Callable[[ResearchGraphState], dict[str, Any]],
        search_node: Callable[[ResearchGraphState], dict[str, Any]],
        summarize_node: Callable[[ResearchGraphState], dict[str, Any]],
        report_node: Callable[[ResearchGraphState], dict[str, Any]],
        max_loops: int = 3,
    ) -> None:
        self.max_loops = max_loops
        self.plan_node = plan_node
        self.search_node = search_node
        self.summarize_node = summarize_node
        self.report_node = report_node
        self._graph = self._build_graph()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ResearchGraphState)

        # Add nodes
        workflow.add_node("plan", self.plan_node)
        workflow.add_node("search", self.search_node)
        workflow.add_node("summarize", self.summarize_node)
        workflow.add_node("report", self.report_node)

        # Entry
        workflow.set_entry_point("plan")

        # Edges
        workflow.add_edge("plan", "search")
        workflow.add_edge("search", "summarize")
        workflow.add_conditional_edges(
            "summarize",
            self._should_continue,
            {"continue": "search", "report": "report"},
        )
        workflow.add_edge("report", END)

        return workflow.compile()

    # ------------------------------------------------------------------
    # Conditional routing
    # ------------------------------------------------------------------

    def _should_continue(self, state: ResearchGraphState) -> str:
        if state.error:
            return "report"
        if state.current_task_index >= len(state.todo_items):
            if state.research_loop_count >= state.max_loops:
                return "report"
            # More loops requested — reset to first task
            state.current_task_index = 0
            state.research_loop_count += 1
            return "search" if state.todo_items else "report"
        return "search"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, topic: str, search_api: str = "", max_loops: int = 3) -> ResearchGraphState:
        """Synchronous execution."""
        initial = ResearchGraphState(
            research_topic=topic,
            search_api=search_api,
            max_loops=max_loops or self.max_loops,
        )
        result = self._graph.invoke(initial)
        return result

    async def arun(
        self, topic: str, search_api: str = "", max_loops: int = 3
    ) -> ResearchGraphState:
        """Async execution."""
        initial = ResearchGraphState(
            research_topic=topic,
            search_api=search_api,
            max_loops=max_loops or self.max_loops,
        )
        result = await self._graph.ainvoke(initial)
        return result

    async def astream(
        self, topic: str, search_api: str = "", max_loops: int = 3
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream graph execution events."""
        initial = ResearchGraphState(
            research_topic=topic,
            search_api=search_api,
            max_loops=max_loops or self.max_loops,
        )
        async for event in self._graph.astream(initial):
            yield event

    def get_graph(self):
        """Return the compiled graph for visualization."""
        return self._graph
