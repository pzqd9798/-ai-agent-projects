"""高德地图 API 服务封装 - 直接 HTTPS 调用，不依赖 MCP"""
import requests
from typing import List, Optional, Dict, Any
from ..config import get_settings


class AmapService:
    """高德地图 Web API 封装"""

    BASE_URL = "https://restapi.amap.com/v3"

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.amap_api_key

    def _get(self, endpoint: str, params: Dict[str, Any]) -> dict:
        params["key"] = self.api_key
        resp = requests.get(f"{self.BASE_URL}{endpoint}", params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "1":
            raise RuntimeError(f"高德API错误: {data.get('info', 'unknown')}")
        return data

    # ---- POI 搜索 ----

    def text_search(self, keywords: str, city: str, citylimit: bool = True,
                    offset: int = 10) -> List[dict]:
        """POI 关键字搜索"""
        data = self._get("/place/text", {
            "keywords": keywords,
            "city": city,
            "citylimit": str(citylimit).lower(),
            "offset": offset,
            "extensions": "all",
        })
        pois = data.get("pois", [])
        return [
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "address": p.get("address"),
                "location": {
                    "longitude": float(p.get("location", "0,0").split(",")[0]),
                    "latitude": float(p.get("location", "0,0").split(",")[1]),
                },
                "category": p.get("type", "").split(";")[-1] if p.get("type") else "",
                "rating": float(p.get("biz_ext", {}).get("rating", 0)) if p.get("biz_ext") else None,
                "photos": [pic.get("url") for pic in p.get("photos", [])[:3]] if p.get("photos") else [],
            }
            for p in pois
        ]

    # ---- 天气查询 ----

    def weather_info(self, city: str) -> List[dict]:
        """查询天气预报"""
        # 先获取城市 adcode
        data = self._get("/config/district", {"keywords": city, "subdistrict": 0})
        districts = data.get("districts", [])
        if not districts:
            raise ValueError(f"未找到城市: {city}")
        adcode = districts[0].get("adcode")

        # 查询天气
        data = self._get("/weather/weatherInfo", {"city": adcode, "extensions": "all"})
        forecasts = data.get("forecasts", [])
        if not forecasts:
            return []
        return [
            {
                "date": cast.get("date"),
                "day_weather": cast.get("dayweather", ""),
                "night_weather": cast.get("nightweather", ""),
                "day_temp": int(cast.get("daytemp", 0)),
                "night_temp": int(cast.get("nighttemp", 0)),
                "wind_direction": cast.get("daywind", ""),
                "wind_power": cast.get("daypower", ""),
            }
            for cast in forecasts[0].get("casts", [])
        ]

    # ---- 路线规划 ----

    def walking_route(self, origin: str, destination: str) -> dict:
        """步行路线规划"""
        data = self._get("/direction/walking", {"origin": origin, "destination": destination})
        route = data.get("route", {})
        paths = route.get("paths", [])
        return {"distance": int(paths[0].get("distance", 0)), "duration": int(paths[0].get("duration", 0))} if paths else {}


# 单例
_amap_service: AmapService | None = None


def get_amap_service() -> AmapService:
    global _amap_service
    if _amap_service is None:
        _amap_service = AmapService()
    return _amap_service
