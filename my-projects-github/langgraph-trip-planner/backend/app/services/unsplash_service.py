"""图片服务 —— 基于高德 POI 自带的照片数据"""
from typing import List, Optional
from .amap_service import get_amap_service


class PhotoService:
    """使用高德地图 POI 搜索获取景点照片（零额外 API 依赖）"""

    def search_photos(self, query: str, per_page: int = 5) -> List[dict]:
        """通过高德 POI 搜索获取照片"""
        try:
            amap = get_amap_service()
            pois = amap.text_search(keywords=query, city="", citylimit=False, offset=per_page)
            photos = []
            for poi in pois:
                for url in poi.get("photos", []):
                    photos.append({
                        "id": poi.get("id", ""),
                        "url": url,
                        "thumb": url.replace("?operate=merge", "?operate=merge&thumbnail=1"),
                        "description": poi.get("name", ""),
                        "photographer": "高德地图",
                    })
            return photos[:per_page]
        except Exception as e:
            print(f"❌ 高德图片搜索失败: {e}")
            return []

    def get_photo_url(self, query: str) -> Optional[str]:
        photos = self.search_photos(query, per_page=1)
        return photos[0]["url"] if photos else None


_photo_service: PhotoService | None = None


def get_photo_service() -> PhotoService:
    global _photo_service
    if _photo_service is None:
        _photo_service = PhotoService()
    return _photo_service


# 保持向后兼容的别名
get_unsplash_service = get_photo_service

