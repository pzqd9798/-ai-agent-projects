"""arq 异步 Worker — 处理耗时任务.

启动: arq app.worker.tasks.WorkerSettings

任务:
    - ingest_document: 异步摄取大文件
    - rebuild_index: 重建知识库索引
    - cleanup_old_sessions: 清理过期会话
"""

import os
import asyncio
from pathlib import Path

from arq.connections import RedisSettings

from app.config import infra


# ---------------------------------------------------------------------------
# Redis 配置
# ---------------------------------------------------------------------------

class WorkerSettings:
    """arq Worker 配置."""
    redis_settings = RedisSettings.from_dsn(infra.redis_url)
    functions = []
    max_jobs = 10
    job_timeout = 600  # 10 分钟
    poll_delay = 0.5


# ---------------------------------------------------------------------------
# 任务
# ---------------------------------------------------------------------------

async def ingest_document(ctx, file_path: str, kb_id: int):
    """异步摄取文档 (大文件不阻塞主请求).

    在 worker 进程内执行，完成后更新数据库状态。
    """
    # 在 worker 内创建独立事件循环
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.database import init_db, Document
    from app.engine.rag_pipeline import RAGPipeline
    from app.engine.chunker import AdaptiveChunker
    from app.services.ingestion import DocumentLoader

    # 初始化数据库
    engine = await init_db()
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    loader = DocumentLoader()
    chunker = AdaptiveChunker()

    async with session_factory() as db:
        from sqlalchemy import select

        # 更新状态为 processing
        result = await db.execute(
            select(Document).where(Document.filename == Path(file_path).name)
        )
        doc = result.scalar_one_or_none()

        if doc:
            doc.status = "processing"
            await db.commit()

        # 加载、分块、嵌入
        try:
            text, meta = loader.load(file_path)
            chunks = chunker.chunk(text, source=Path(file_path).name)

            # 更新文档
            if doc:
                doc.status = "ready"
                doc.file_size = len(text.encode("utf-8"))
                await db.commit()

            return {
                "status": "ok",
                "filename": Path(file_path).name,
                "chunks": len(chunks),
            }
        except Exception as exc:
            if doc:
                doc.status = "error"
                await db.commit()
            return {"status": "error", "error": str(exc)}


async def rebuild_index(ctx, kb_id: int):
    """重建知识库的完整索引."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.database import init_db, Document, Chunk
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    engine = await init_db()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        result = await db.execute(
            select(Chunk).where(
                Chunk.doc_id.in_(select(Document.id).where(Document.kb_id == kb_id))
            )
        )
        chunks = result.scalars().all()

        # 重新嵌入
        from app.engine.rag_pipeline import RAGPipeline
        from app.engine.chunker import ChunkData

        pipeline = RAGPipeline()
        chunk_data = [ChunkData(
            id=c.id, text=c.text, source="",
            chunk_index=c.chunk_index, metadata=c.metadata_,
        ) for c in chunks]
        pipeline.index_chunks(chunk_data)

        # 更新数据库中的 embedding
        for c, cd in zip(chunks, chunk_data):
            c.embedding = cd.embedding
            db.add(c)

        await db.commit()

        return {"status": "ok", "reindexed_chunks": len(chunks)}


async def cleanup_old_sessions(ctx, days: int = 30):
    """清理过期会话."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.database import init_db, ChatSession
    from sqlalchemy import select, delete
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from datetime import datetime, timedelta

    engine = await init_db()
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    cutoff = datetime.utcnow() - timedelta(days=days)

    async with session_factory() as db:
        result = await db.execute(
            delete(ChatSession).where(ChatSession.updated_at < cutoff)
        )
        await db.commit()
        deleted = result.rowcount

        return {"status": "ok", "deleted_sessions": deleted}
