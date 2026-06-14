"""文档摄取服务 — 加载 → 分块 → 索引 → 持久化."""

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Document, Chunk, KnowledgeBase
from app.engine.chunker import AdaptiveChunker, ChunkData
from app.engine.rag_pipeline import RAGPipeline
from app.services.observability import get_logger, get_metrics


logger = get_logger()
metrics = get_metrics()


# ---------------------------------------------------------------------------
# 文档加载器
# ---------------------------------------------------------------------------

class DocumentLoader:
    """加载各种格式的文档为纯文本."""

    @staticmethod
    def load(file_path: str | Path) -> tuple[str, dict]:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".txt":
            return path.read_text(encoding="utf-8"), {"format": "txt"}

        elif suffix == ".md":
            text = path.read_text(encoding="utf-8")
            import re
            title = ""
            m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            if m:
                title = m.group(1)
            return text, {"format": "markdown", "title": title}

        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t:
                        pages.append(t)
                text = "\n\n".join(pages)
                meta_src = reader.metadata or {}
                return text, {
                    "format": "pdf",
                    "title": str(getattr(meta_src, "title", "")),
                    "pages": len(reader.pages),
                    "author": str(getattr(meta_src, "author", "")),
                }
            except ImportError:
                raise ImportError("请安装 pypdf: pip install pypdf")

        else:
            raise ValueError(f"不支持的格式: {suffix}")


# ---------------------------------------------------------------------------
# 摄取服务
# ---------------------------------------------------------------------------

class IngestionService:
    """文档摄取服务 — 加载、分块、嵌入、持久化."""

    def __init__(self, pipeline: RAGPipeline):
        self.pipeline = pipeline
        self.chunker = AdaptiveChunker()
        self.loader = DocumentLoader()

    async def ingest_file(
        self,
        file_path: str,
        kb_id: int,
        db: AsyncSession,
    ) -> dict:
        """摄取单个文件: 加载 → 分块 → 嵌入 → 写入数据库."""
        path = Path(file_path)
        filename = path.name
        t0 = __import__("time").time()

        logger.info("ingest_start", file=filename, kb_id=kb_id)

        # 1. 加载文档
        text, meta = self.loader.load(file_path)
        file_size = len(text.encode("utf-8"))

        # 2. 创建文档记录
        doc = Document(
            kb_id=kb_id,
            filename=filename,
            format=meta.get("format", "unknown"),
            file_size=file_size,
            status="processing",
            metadata_=meta,
        )
        db.add(doc)
        await db.flush()

        # 3. 分块
        chunks_data = self.chunker.chunk(text, source=filename)

        # 4. 嵌入 + 写入数据库
        chunk_models = []
        for cd in chunks_data:
            chunk_models.append(Chunk(
                id=cd.id,
                doc_id=doc.id,
                text=cd.text,
                chunk_index=cd.chunk_index,
                metadata_=cd.metadata,
            ))

        # 批量嵌入
        try:
            self.pipeline.index_chunks(chunks_data)
            # 保存 embedding
            for cm, cd in zip(chunk_models, chunks_data):
                cm.embedding = cd.embedding
        except Exception as exc:
            logger.error("embedding_failed", file=filename, error=str(exc))
            # 继续 — 没有 embedding 也能做 BM25 检索

        db.add_all(chunk_models)

        # 5. 更新文档状态并提交
        doc.status = "ready"
        await db.commit()

        elapsed = (__import__("time").time() - t0) * 1000
        logger.info(
            "ingest_done", file=filename, chunks=len(chunks_data),
            elapsed_ms=round(elapsed, 1),
        )
        metrics.incr("documents_ingested")
        metrics.incr("chunks_created", len(chunks_data))

        return {
            "doc_id": doc.id,
            "filename": filename,
            "chunks": len(chunks_data),
            "format": meta.get("format"),
            "elapsed_ms": round(elapsed, 1),
        }

    async def ingest_directory(
        self,
        dir_path: str,
        kb_id: int,
        db: AsyncSession,
    ) -> list[dict]:
        """批量摄取目录中的文档."""
        results = []
        base = Path(dir_path)

        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in (".txt", ".md", ".pdf"):
                try:
                    result = await self.ingest_file(str(path), kb_id, db)
                    results.append(result)
                except Exception as exc:
                    logger.error("ingest_error", file=path.name, error=str(exc))
                    results.append({
                        "filename": path.name,
                        "error": str(exc),
                        "chunks": 0,
                    })

        return results
