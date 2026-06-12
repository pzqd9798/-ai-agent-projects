"""地图服务 API 路由"""
from fastapi import APIRouter, HTTPException, Query
from ...services.amap_service import get_amap_service

router = APIRouter(prefix="/map", tags=["地图服务"])


@router.get("/weather", summary="查询天气")
async def get_weather(city: str = Query(..., examples=["北京"])):
    try:
        service = get_amap_service()
        data = service.weather_info(city)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"天气查询失败: {e}")


@router.get("/route", summary="路线规划")
async def get_route(
    origin: str = Query(...), destination: str = Query(...)
):
    try:
        service = get_amap_service()
        data = service.walking_route(origin, destination)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"路线规划失败: {e}")
