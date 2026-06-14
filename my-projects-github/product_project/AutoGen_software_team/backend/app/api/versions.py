"""版本 API — 快照创建/列表/对比/回退."""

from fastapi import APIRouter, HTTPException, Depends, Query

from app.api.auth import get_current_user
from app.services.versioning import get_version_manager

router = APIRouter(prefix="/api/projects", tags=["版本管理"])


@router.post("/{project_id}/versions")
async def create_version(project_id: str, message: str = "",
                         user=Depends(get_current_user)):
    """为当前项目产物创建版本快照."""
    vm = get_version_manager()
    try:
        result = await vm.create_snapshot(project_id, message)
        return result
    except Exception as e:
        raise HTTPException(500, f"版本创建失败: {str(e)}")


@router.get("/{project_id}/versions")
async def list_versions(project_id: str, user=Depends(get_current_user)):
    """列出项目的所有版本."""
    vm = get_version_manager()
    return await vm.list_versions(project_id)


@router.get("/{project_id}/versions/{version_number}")
async def get_version(project_id: str, version_number: int,
                      user=Depends(get_current_user)):
    """获取指定版本的完整快照."""
    vm = get_version_manager()
    snapshot = await vm.get_version(project_id, version_number)
    if not snapshot:
        raise HTTPException(404, "版本不存在")
    return snapshot


@router.get("/{project_id}/versions/diff")
async def diff_versions(project_id: str,
                        from_ver: int = Query(...),
                        to_ver: int = Query(...),
                        user=Depends(get_current_user)):
    """对比两个版本之间的文件差异."""
    vm = get_version_manager()
    return await vm.diff_versions(project_id, from_ver, to_ver)


@router.post("/{project_id}/versions/{version_number}/rollback")
async def rollback_version(project_id: str, version_number: int,
                           user=Depends(get_current_user)):
    """回退到指定版本."""
    vm = get_version_manager()
    try:
        restored = await vm.rollback(project_id, version_number)
        return {"ok": True, "restored_files": len(restored), "files": restored}
    except Exception as e:
        raise HTTPException(500, f"回退失败: {str(e)}")
