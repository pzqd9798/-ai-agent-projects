"""WebSocket API — SSE 流式 RAG 回答."""

import asyncio
import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import llm
from app.database import User, KnowledgeBase, Document, Chunk, ChatSession, ChatMessage, get_db
from app.api.auth import get_current_user
from app.api.chat import get_pipeline
from app.services.memory_service import MemoryManager

import anthropic

router = APIRouter(prefix="/ws", tags=["流式"])


@router.get("/chat/stream")
async def chat_stream(
    question: str = Query(..., min_length=1),
    kb_id: int = Query(None),
    session_id: int = Query(None),
    top_k: int = Query(5),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式 RAG 问答 — 实时推送生成的每一个 token."""

    # 1. 确定知识库
    if kb_id:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id, KnowledgeBase.user_id == user.id,
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
    else:
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
        )
        kb = result.scalars().first()
        if not kb:
            raise HTTPException(status_code=400, detail="没有可用的知识库")

    # 2. 会话
    session = None
    if session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()

    if session is None:
        session = ChatSession(
            user_id=user.id, kb_id=kb.id,
            title=question[:50] + ("..." if len(question) > 50 else ""),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # 3. 检索
    pipeline = await get_pipeline(kb.id, db)
    retrieved = pipeline.retrieve(question, top_k=top_k)

    # 4. 记忆上下文
    memory_manager = MemoryManager(user.id, db)
    await memory_manager.long_term.load()
    memory_context = await memory_manager.long_term.build_context_text()

    # 5. 构建消息
    context = pipeline._build_context(question, retrieved, memory_context)

    # 获取历史消息
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history = result.scalars().all()
    messages = [{"role": m.role, "content": m.content} for m in reversed(history)]
    messages.append({"role": "user", "content": context})

    # 6. 保存用户消息
    user_msg = ChatMessage(session_id=session.id, role="user", content=question)
    db.add(user_msg)
    await db.commit()

    # 7. SSE 生成器
    async def event_generator():
        import os
        t0 = time.time()
        full_answer = ""

        try:
            client = anthropic.Anthropic(
                api_key=llm.api_key or os.getenv("ANTHROPIC_API_KEY", ""),
                base_url=llm.base_url or os.getenv("ANTHROPIC_BASE_URL") or None,
            )

            yield {
                "event": "status",
                "data": json.dumps({
                    "phase": "retrieval_done",
                    "retrieved_count": len(retrieved),
                    "sources": [
                        {"filename": c.source, "chunk_index": c.chunk_index,
                         "score": round(s, 4)}
                        for c, s in retrieved
                    ],
                }, ensure_ascii=False),
            }

            # 流式 LLM 调用
            stream = client.messages.create(
                model=llm.model_id,
                max_tokens=llm.max_tokens,
                system=pipeline.system_prompt,
                messages=messages,
                stream=True,
            )

            for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        token = event.delta.text
                        full_answer += token
                        yield {
                            "event": "token",
                            "data": json.dumps({"token": token}, ensure_ascii=False),
                        }

            # 发送完成事件
            elapsed = (time.time() - t0) * 1000
            yield {
                "event": "done",
                "data": json.dumps({
                    "elapsed_ms": round(elapsed, 1),
                    "total_tokens": len(full_answer) // 4,
                }, ensure_ascii=False),
            }

            # 保存回答
            async for _db in db:
                assistant_msg = ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content=full_answer,
                    sources=[
                        {"filename": c.source, "chunk_index": c.chunk_index, "score": round(s, 4)}
                        for c, s in retrieved
                    ],
                    elapsed_ms=elapsed,
                )
                _db.add(assistant_msg)
                await _db.commit()
                break

            # 更新记忆
            await memory_manager.add_user_message(question)
            await memory_manager.add_assistant_message(full_answer)
            await memory_manager.long_term.auto_extract(question, full_answer)

        except Exception as exc:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(exc)}, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
