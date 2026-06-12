"""数据模型定义 - 与原版完全兼容"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import date


# ============ 请求模型 ============

class TripRequest(BaseModel):
    """旅行规划请求"""
    city: str = Field(..., description="目的地城市", example="北京")
    start_date: str = Field(..., description="开始日期 YYYY-MM-DD", example="2025-06-01")
    end_date: str = Field(..., description="结束日期 YYYY-MM-DD", example="2025-06-03")
    travel_days: int = Field(..., ge=1, le=30, example=3)
    transportation: str = Field(..., description="交通方式", example="公共交通")
    accommodation: str = Field(..., description="住宿偏好", example="经济型酒店")
    preferences: List[str] = Field(default=[], description="偏好标签", example=["历史文化", "美食"])
    free_text_input: Optional[str] = Field(default="", description="额外要求")

    class Config:
        json_schema_extra = {
            "example": {
                "city": "北京", "start_date": "2025-06-01", "end_date": "2025-06-03",
                "travel_days": 3, "transportation": "公共交通", "accommodation": "经济型酒店",
                "preferences": ["历史文化", "美食"], "free_text_input": "希望多安排博物馆"
            }
        }


# ============ 响应模型 ============

class Location(BaseModel):
    longitude: float
    latitude: float


class Attraction(BaseModel):
    name: str
    address: str
    location: Location
    visit_duration: int = Field(..., description="建议游览时间(分钟)")
    description: str
    category: Optional[str] = "景点"
    rating: Optional[float] = None
    image_url: Optional[str] = None
    ticket_price: int = 0


class Meal(BaseModel):
    type: str = Field(..., description="breakfast/lunch/dinner/snack")
    name: str
    address: Optional[str] = None
    location: Optional[Location] = None
    description: Optional[str] = None
    estimated_cost: int = 0


class Hotel(BaseModel):
    name: str
    address: str = ""
    location: Optional[Location] = None
    price_range: str = ""
    rating: str = ""
    distance: str = ""
    type: str = ""
    estimated_cost: int = 0


class DayPlan(BaseModel):
    date: str
    day_index: int
    description: str
    transportation: str
    accommodation: str
    hotel: Optional[Hotel] = None
    attractions: List[Attraction] = []
    meals: List[Meal] = []


class WeatherInfo(BaseModel):
    date: str
    day_weather: str
    night_weather: str
    day_temp: int
    night_temp: int
    wind_direction: str
    wind_power: str


class Budget(BaseModel):
    total_attractions: int = 0
    total_hotels: int = 0
    total_meals: int = 0
    total_transportation: int = 0
    total: int = 0


class TripPlan(BaseModel):
    city: str
    start_date: str
    end_date: str
    days: List[DayPlan] = []
    weather_info: List[WeatherInfo] = []
    overall_suggestions: str = ""
    budget: Optional[Budget] = None


class TripPlanResponse(BaseModel):
    success: bool
    message: str
    data: Optional[TripPlan] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[str] = None
