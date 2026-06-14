"""文档管理 API — 上传、列表、删除、纯检索."""

import tempfile
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import User, KnowledgeBase, Document, Chunk, get_db
from app.api.auth import get_current_user
from app.services.ingestion import IngestionService
from app.engine.rag_pipeline import RAGPipeline
from app.api.chat import get_pipeline
from app.services.observability import get_logger, get_metrics
from app.models.schemas import (
    DocumentResponse, DocumentUploadResponse,
    SearchRequest, SearchResponse, SearchResult,
)

router = APIRouter(prefix="/api/documents", tags=["文档"])

logger = get_logger()
metrics = get_metrics()

# 允许的文件类型
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    kb_id: int = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文档到指定知识库."""
    # 1. 校验知识库所有权
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 2. 校验文件类型
    suffix = Path(file.filename).suffix.lower() if file.filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {suffix}。支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 3. 保存临时文件
    upload_dir = Path(__file__).resolve().parent.parent.parent / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = upload_dir / f"{user.id}_{kb_id}_{file.filename}"

    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        # 4. 摄取文档
        pipeline = await get_pipeline(kb_id, db)
        ingestion = IngestionService(pipeline)
        result = await ingestion.ingest_file(str(tmp_path), kb_id, db)

        return DocumentUploadResponse(
            id=result["doc_id"],
            filename=result["filename"],
            status="ready",
            message=f"已索引 {result['chunks']} 个片段",
        )
    except Exception as exc:
        logger.error("upload_failed", filename=file.filename, error=str(exc))
        raise HTTPException(status_code=500, detail=f"文档处理失败: {exc}")
    finally:
        # 清理临时文件
        if tmp_path.exists():
            tmp_path.unlink()


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识库下的文档列表."""
    # 校验所有权
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")

    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id).order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()

    responses = []
    for doc in docs:
        chunk_count = (await db.execute(
            select(func.count(Chunk.id)).where(Chunk.doc_id == doc.id)
        )).scalar() or 0
        responses.append(DocumentResponse(
            id=doc.id,
            filename=doc.filename,
            format=doc.format,
            file_size=doc.file_size,
            status=doc.status,
            chunk_count=chunk_count,
            metadata=doc.metadata_,
            created_at=doc.created_at,
        ))

    return responses


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: int,
    kb_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文档及关联 chunks."""
    # 校验所有权
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="知识库不存在")

    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.kb_id == kb_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    await db.delete(doc)
    await db.commit()

    logger.info("document_deleted", doc_id=doc_id, filename=doc.filename)

    return {"message": f"文档 '{doc.filename}' 已删除"}


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    req: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """纯检索 — 不生成回答，只返回相关片段."""
    # 确定知识库
    kb_id = req.kb_id
    if not kb_id:
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
        )
        kb = result.scalars().first()
        if not kb:
            raise HTTPException(status_code=400, detail="没有可用的知识库")
        kb_id = kb.id

    import time
    t0 = time.time()

    pipeline = await get_pipeline(kb_id, db)
    results = pipeline.search(req.query, top_k=req.top_k)

    elapsed = (time.time() - t0) * 1000

    return SearchResponse(
        query=req.query,
        results=[
            SearchResult(
                chunk_id=r["chunk_id"],
                text=r["text"],
                source=r["source"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in results
        ],
        total=len(results),
        elapsed_ms=elapsed,
    )
