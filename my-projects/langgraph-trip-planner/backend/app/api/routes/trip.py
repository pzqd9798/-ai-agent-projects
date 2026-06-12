"""旅行规划 API 路由"""
import uuid
import re

from fastapi import APIRouter, HTTPException
from ...models.schemas import TripRequest, TripPlanResponse, TripPlan
from ...agents.trip_graph import get_compiled_graph

router = APIRouter(prefix="/trip", tags=["旅行规划"])


def _sanitize_plan(plan: dict, expected_days: int = 99) -> dict:
    """清洗 LLM 输出的不规范字段，使其符合 Pydantic Schema"""
    if not isinstance(plan, dict):
        return plan

    # 1. budget 字符串 → None
    if isinstance(plan.get("budget"), str):
        plan["budget"] = None

    # 2. 截断多余的天数
    days = plan.get("days", [])
    if len(days) > expected_days:
        plan["days"] = days[:expected_days]
        days = plan["days"]

    for day in days:
        # 3. accommodation: dict → str（LLM 有时输出 {"name":"...","check_out":"..."}）
        acc = day.get("accommodation")
        if isinstance(acc, dict):
            day["accommodation"] = acc.get("name", str(acc))
        elif not isinstance(acc, str):
            day["accommodation"] = str(acc) if acc else "待推荐"

        # 4. hotel.rating: float → str
        hotel = day.get("hotel", {})
        if isinstance(hotel, dict):
            if isinstance(hotel.get("rating"), (int, float)):
                hotel["rating"] = str(hotel["rating"])
            # 5. hotel 完全缺失 → 占位
            if not hotel:
                day["hotel"] = {
                    "name": "待推荐", "address": "", "price_range": "",
                    "rating": "4.0", "type": "经济型", "estimated_cost": 300
                }

        # 6. attractions 类型修复
        for attr in day.get("attractions", []):
            dur = attr.get("visit_duration")
            if isinstance(dur, str):
                m = re.match(r'(\d+(?:\.\d+)?)\s*小时', dur)
                attr["visit_duration"] = int(float(m.group(1)) * 60) if m else 60
            price = attr.get("ticket_price")
            if isinstance(price, str):
                m = re.search(r'(\d+)', price)
                attr["ticket_price"] = int(m.group(1)) if m else 0

        # 7. meals: restaurant → name
        for meal in day.get("meals", []):
            if "restaurant" in meal and "name" not in meal:
                meal["name"] = meal.pop("restaurant")
            if "name" not in meal:
                meal["name"] = "当地推荐"

    return plan


def _request_to_state(request: TripRequest) -> dict:
    """将 Pydantic 请求转为 LangGraph 初始状态"""
    return {
        "city": request.city,
        "start_date": request.start_date,
        "end_date": request.end_date,
        "travel_days": request.travel_days,
        "transportation": request.transportation,
        "accommodation": request.accommodation,
        "preferences": request.preferences,
        "free_text_input": request.free_text_input or "",
    }


@router.post("/plan", response_model=TripPlanResponse, summary="生成旅行计划 (LangGraph版)")
async def plan_trip(request: TripRequest):
    """
    使用 LangGraph 状态图生成旅行计划。

    与原版对比:
    - 景点/天气/酒店搜索**并行执行**，响应更快
    - 内置**计划校验 + 自动重试**，质量更高
    - 支持 Checkpoint 中断恢复
    """
    try:
        print(f"\n{'='*60}")
        print(f"📥 [LangGraph] 收到请求: {request.city}, {request.travel_days}天")
        print(f"{'='*60}")

        graph = get_compiled_graph()
        thread_id = str(uuid.uuid4())[:8]
        config = {"configurable": {"thread_id": thread_id}}

        # ★ 核心：执行 LangGraph 状态图
        final_state = graph.invoke(_request_to_state(request), config)

        plan_dict = final_state.get("final_plan", {})
        # 清洗 LLM 输出的不规范字段
        plan_dict = _sanitize_plan(plan_dict, expected_days=request.travel_days)
        plan = TripPlan(**plan_dict)

        print(f"✅ [LangGraph] 计划生成成功: {len(plan.days)}天\n")

        return TripPlanResponse(success=True, message="旅行计划生成成功 (LangGraph)", data=plan)

    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@router.get("/health", summary="健康检查")
async def health_check():
    try:
        graph = get_compiled_graph()
        return {
            "status": "healthy",
            "service": "trip-planner-langgraph",
            "engine": "LangGraph StateGraph",
            "features": ["parallel_search", "auto_retry", "checkpoint"],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"服务不可用: {e}")
