"""知识库 API — CRUD + 统计."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import User, KnowledgeBase, Document, Chunk, get_db
from app.api.auth import get_current_user
from app.models.schemas import (
    KBCreateRequest, KBUpdateRequest, KBResponse,
)

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


# ---------------------------------------------------------------------------
# 依赖 — 获取用户的知识库 (带权限校验)
# ---------------------------------------------------------------------------

async def get_user_kb(
    kb_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeBase:
    result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.user_id == user.id,
        )
    )
    kb = result.scalar_one_or_none()
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return kb


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post("", response_model=KBResponse)
async def create_kb(
    req: KBCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库."""
    kb = KnowledgeBase(
        user_id=user.id,
        name=req.name,
        description=req.description,
        tags=req.tags,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    return KBResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        tags=kb.tags,
        document_count=0,
        chunk_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get("", response_model=list[KBResponse])
async def list_kbs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取用户的所有知识库."""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.user_id == user.id)
    )
    kbs = result.scalars().all()

    responses = []
    for kb in kbs:
        # 统计文档数和 chunk 数
        doc_count = (await db.execute(
            select(func.count(Document.id)).where(Document.kb_id == kb.id)
        )).scalar() or 0

        chunk_count = (await db.execute(
            select(func.count(Chunk.id)).where(
                Chunk.doc_id.in_(
                    select(Document.id).where(Document.kb_id == kb.id)
                )
            )
        )).scalar() or 0

        responses.append(KBResponse(
            id=kb.id,
            name=kb.name,
            description=kb.description,
            tags=kb.tags,
            document_count=doc_count,
            chunk_count=chunk_count,
            created_at=kb.created_at,
            updated_at=kb.updated_at,
        ))

    return responses


@router.get("/{kb_id}", response_model=KBResponse)
async def get_kb(kb: KnowledgeBase = Depends(get_user_kb),
                 db: AsyncSession = Depends(get_db)):
    """获取知识库详情."""
    doc_count = (await db.execute(
        select(func.count(Document.id)).where(Document.kb_id == kb.id)
    )).scalar() or 0

    chunk_count = (await db.execute(
        select(func.count(Chunk.id)).where(
            Chunk.doc_id.in_(
                select(Document.id).where(Document.kb_id == kb.id)
            )
        )
    )).scalar() or 0

    return KBResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        tags=kb.tags,
        document_count=doc_count,
        chunk_count=chunk_count,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.put("/{kb_id}", response_model=KBResponse)
async def update_kb(
    req: KBUpdateRequest,
    kb: KnowledgeBase = Depends(get_user_kb),
    db: AsyncSession = Depends(get_db),
):
    """更新知识库."""
    if req.name is not None:
        kb.name = req.name
    if req.description is not None:
        kb.description = req.description
    if req.tags is not None:
        kb.tags = req.tags

    db.add(kb)
    await db.commit()
    await db.refresh(kb)

    return KBResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        tags=kb.tags,
        document_count=0,
        chunk_count=0,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.delete("/{kb_id}")
async def delete_kb(
    kb: KnowledgeBase = Depends(get_user_kb),
    db: AsyncSession = Depends(get_db),
):
    """删除知识库及其所有文档和 chunks."""
    await db.delete(kb)
    await db.commit()
    return {"message": "知识库已删除", "kb_id": kb.id}
