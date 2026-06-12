"""POI API 路由"""
from fastapi import APIRouter, HTTPException
from ...services.amap_service import get_amap_service
from ...services.unsplash_service import get_photo_service

router = APIRouter(prefix="/poi", tags=["POI"])


@router.get("/search", summary="搜索 POI")
async def search_poi(keywords: str, city: str = "北京"):
    try:
        service = get_amap_service()
        pois = service.text_search(keywords, city)
        return {"success": True, "message": "搜索成功", "data": pois}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"POI搜索失败: {e}")


@router.get("/photo", summary="获取景点图片（高德 POI）")
async def get_attraction_photo(name: str):
    try:
        ps = get_photo_service()
        url = ps.get_photo_url(name)
        return {"success": True, "data": {"image_url": url}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片获取失败: {e}")
