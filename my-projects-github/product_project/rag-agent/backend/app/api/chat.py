"""对话 API — RAG 问答 + 会话管理."""

import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    User, KnowledgeBase, Document, Chunk,
    ChatSession, ChatMessage, get_db,
)
from app.api.auth import get_current_user
from app.engine.rag_pipeline import RAGPipeline
from app.engine.chunker import ChunkData
from app.services.memory_service import MemoryManager
from app.services.observability import get_logger, get_metrics
from app.models.schemas import (
    ChatRequest, ChatResponse, SourceInfo,
    ChatSessionResponse, ChatMessageResponse,
)

router = APIRouter(prefix="/api/chat", tags=["对话"])

logger = get_logger()
metrics = get_metrics()


# ---------------------------------------------------------------------------
# 知识库管道缓存 (按 kb_id)
# ---------------------------------------------------------------------------

_pipeline_cache: dict[int, RAGPipeline] = {}


async def get_pipeline(kb_id: int, db: AsyncSession) -> RAGPipeline:
    """获取或构建某个知识库的 RAG 管道."""
    if kb_id in _pipeline_cache:
        return _pipeline_cache[kb_id]

    pipeline = RAGPipeline()

    # 从数据库加载所有 chunks
    result = await db.execute(
        select(Chunk).where(
            Chunk.doc_id.in_(
                select(Document.id).where(Document.kb_id == kb_id)
            )
        )
    )
    chunks = result.scalars().all()

    if chunks:
        chunk_data = []
        for c in chunks:
            cd = ChunkData(
                id=c.id, text=c.text, source=c.document.filename if c.document else "",
                chunk_index=c.chunk_index, metadata=c.metadata_,
            )
            if c.embedding:
                cd.embedding = c.embedding
            chunk_data.append(cd)
        pipeline.index_chunks(chunk_data)

    _pipeline_cache[kb_id] = pipeline
    return pipeline


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """RAG 问答 — 检索 + 生成."""
    t0 = time.time()

    # 1. 确定知识库
    kb = None
    if req.kb_id:
        result = await db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == req.kb_id,
                KnowledgeBase.user_id == user.id,
            )
        )
        kb = result.scalar_one_or_none()
        if not kb:
            raise HTTPException(status_code=404, detail="知识库不存在")
    else:
        # 使用最近的知识库
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
        )
        kb = result.scalars().first()
        if not kb:
            raise HTTPException(
                status_code=400,
                detail="没有可用的知识库，请先上传文档",
            )

    # 2. 确定或创建会话
    session = None
    if req.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == req.session_id,
                ChatSession.user_id == user.id,
            )
        )
        session = result.scalar_one_or_none()

    if session is None:
        session = ChatSession(
            user_id=user.id,
            kb_id=kb.id,
            title=req.question[:50] + ("..." if len(req.question) > 50 else ""),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

    # 3. 获取 RAG 管道
    pipeline = await get_pipeline(kb.id, db)

    # 4. 获取历史消息
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(20)
    )
    history = result.scalars().all()
    history_messages = []
    for msg in reversed(history):
        history_messages.append({"role": msg.role, "content": msg.content})

    # 5. 获取长期记忆上下文
    memory_manager = MemoryManager(user.id, db)
    await memory_manager.long_term.load()
    memory_context = await memory_manager.long_term.build_context_text()

    # 6. 执行 RAG
    result_rag = pipeline.query(
        req.question,
        top_k=req.top_k,
        context_memory=memory_context,
        history_messages=history_messages,
    )

    # 7. 保存用户消息和回答
    user_msg = ChatMessage(
        session_id=session.id, role="user", content=req.question,
    )
    db.add(user_msg)

    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=result_rag.answer,
        sources=result_rag.sources,
        elapsed_ms=result_rag.elapsed_ms,
    )
    db.add(assistant_msg)

    # 8. 更新记忆
    await memory_manager.add_user_message(req.question)
    await memory_manager.add_assistant_message(result_rag.answer)
    await memory_manager.long_term.auto_extract(req.question, result_rag.answer)

    session.updated_at = func.now()
    await db.commit()

    # 9. 指标
    metrics.incr("chat_queries")
    metrics.incr("tokens_used", len(result_rag.answer) // 4)

    elapsed = (time.time() - t0) * 1000
    logger.info(
        "chat_done", user_id=user.id, kb_id=kb.id,
        session_id=session.id, sources=len(result_rag.sources),
        elapsed_ms=round(elapsed, 1),
    )

    return ChatResponse(
        answer=result_rag.answer,
        sources=[
            SourceInfo(
                filename=s["filename"],
                chunk_index=s["chunk_index"],
                score=s["score"],
                snippet=s["snippet"],
            )
            for s in result_rag.sources
        ],
        retrieved_count=result_rag.retrieved_count,
        elapsed_ms=result_rag.elapsed_ms,
        session_id=session.id,
    )


# ---------------------------------------------------------------------------
# 会话管理
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    kb_id: int | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的会话列表."""
    query = select(ChatSession).where(ChatSession.user_id == user.id)
    if kb_id:
        query = query.where(ChatSession.kb_id == kb_id)
    query = query.order_by(ChatSession.updated_at.desc()).limit(50)

    result = await db.execute(query)
    sessions = result.scalars().all()

    responses = []
    for s in sessions:
        msg_count = (await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.session_id == s.id)
        )).scalar() or 0
        responses.append(ChatSessionResponse(
            id=s.id,
            title=s.title,
            kb_id=s.kb_id,
            message_count=msg_count,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))
    return responses


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话的消息列表."""
    # 校验所有权
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()

    return [
        ChatMessageResponse(
            id=m.id, role=m.role, content=m.content,
            sources=[SourceInfo(**s) for s in (m.sources or [])],
            elapsed_ms=m.elapsed_ms, created_at=m.created_at,
        )
        for m in messages
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话及其消息."""
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    await db.delete(session)
    await db.commit()
    return {"message": "会话已删除"}
