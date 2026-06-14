"""
LangGraph 旅行规划状态图 — 核心编排引擎
========================================
对比原版 HelloAgents 串行调用，LangGraph 版本的三大亮点：
1. 并行执行 —— 景点搜索、天气查询、酒店搜索同时进行
2. 条件路由 —— 计划校验不通过自动重试
3. 可观测性 —— 每个节点的输入/输出可追踪、可中断恢复
"""
import json
import time
import operator
from typing import TypedDict, Annotated, List, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import get_settings
from ..services.llm_service import get_llm
from ..services.amap_service import get_amap_service
from ..models.schemas import TripRequest, TripPlan

# ========== 日志工具 ==========

def _log(step: str, msg: str):
    """统一日志格式"""
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{step}] {msg}")


# ==================== State 定义 ====================

class TripState(TypedDict):
    """LangGraph 全局状态 —— 所有节点共享"""
    # 输入
    city: str
    start_date: str
    end_date: str
    travel_days: int
    transportation: str
    accommodation: str
    preferences: List[str]
    free_text_input: str

    # 搜索结果（并行填充）
    attractions_data: Annotated[list, operator.add]  # 景点列表
    weather_data: Annotated[list, operator.add]      # 天气列表
    hotels_data: Annotated[list, operator.add]        # 酒店列表

    # 计划生成
    final_plan_json: str    # LLM 生成的 JSON 字符串
    final_plan: dict        # 解析后的字典
    retry_count: int        # 重试计数

    # 日志
    logs: Annotated[list, operator.add]


# ==================== 节点函数 ====================

def init_state_node(state: TripState) -> dict:
    """初始化状态并记录日志"""
    _log("INIT", f"开始规划: {state['city']}, {state['travel_days']}天")
    _log("INIT", f"偏好: {state.get('preferences', [])}, 交通: {state['transportation']}, 住宿: {state['accommodation']}")
    return {
        "attractions_data": [],
        "weather_data": [],
        "hotels_data": [],
        "retry_count": 0,
        "logs": [f"🚀 开始规划: {state['city']}, {state['travel_days']}天"],
    }


def search_attractions_node(state: TripState) -> dict:
    """景点搜索节点 —— 调用高德 POI 搜索"""
    t0 = time.time()
    _log("景点搜索", f"开始搜索 {state['city']} 的景点...")
    amap = get_amap_service()
    prefs = state.get("preferences", [])
    city = state["city"]

    all_pois = []
    keywords_list = prefs if prefs else ["景点", "热门景区"]
    for kw in keywords_list[:2]:
        _log("景点搜索", f"  关键词: {kw}")
        pois = amap.text_search(keywords=kw, city=city, offset=8)
        all_pois.extend(pois)

    # 去重
    seen = set()
    unique = []
    for p in all_pois:
        if p["name"] not in seen:
            seen.add(p["name"])
            unique.append(p)

    _log("景点搜索", f"完成 ✅ 找到 {len(unique)} 个景点 (耗时 {time.time()-t0:.1f}s)")
    for p in unique[:3]:
        _log("景点搜索", f"  - {p['name']} ({p.get('address', '无地址')})")

    return {
        "attractions_data": unique,
        "logs": [f"📍 景点搜索完成: {len(unique)} 个结果"],
    }


def query_weather_node(state: TripState) -> dict:
    """天气查询节点"""
    t0 = time.time()
    _log("天气查询", f"开始查询 {state['city']} 天气...")
    amap = get_amap_service()
    weather = amap.weather_info(state["city"])
    
    _log("天气查询", f"完成 ✅ {len(weather)} 天预报 (耗时 {time.time()-t0:.1f}s)")
    for w in weather:
        _log("天气查询", f"  - {w['date']}: {w['day_weather']} {w['day_temp']}°C / {w['night_weather']} {w['night_temp']}°C")

    return {
        "weather_data": weather,
        "logs": [f"🌤️ 天气查询完成: {len(weather)} 天预报"],
    }


def search_hotels_node(state: TripState) -> dict:
    """酒店搜索节点"""
    t0 = time.time()
    keyword = state.get("accommodation", "酒店")
    _log("酒店搜索", f"开始搜索 {state['city']} 的{keyword}...")
    
    amap = get_amap_service()
    hotels = amap.text_search(keywords=keyword, city=state["city"], offset=6)

    _log("酒店搜索", f"完成 ✅ 找到 {len(hotels)} 个酒店 (耗时 {time.time()-t0:.1f}s)")
    for h in hotels[:3]:
        _log("酒店搜索", f"  - {h['name']} ({h.get('address', '无地址')})")

    return {
        "hotels_data": hotels,
        "logs": [f"🏨 酒店搜索完成: {len(hotels)} 个结果"],
    }


def plan_itinerary_node(state: TripState) -> dict:
    """行程规划节点 —— LLM 整合所有信息生成计划"""
    t0 = time.time()
    llm = get_llm()
    settings = get_settings()

    attrs_count = len(state.get("attractions_data", []))
    hotels_count = len(state.get("hotels_data", []))
    weather_count = len(state.get("weather_data", []))
    retry = state.get("retry_count", 0)
    
    _log("LLM规划", f"开始生成行程 (景点:{attrs_count}, 酒店:{hotels_count}, 天气:{weather_count}天, 重试:{retry})")
    _log("LLM规划", "⏳ 正在调用 LLM 生成行程计划... (可能需 20-60 秒)")

    # 格式化搜索结果为 LLM 可读文本
    attrs_str = json.dumps(state.get("attractions_data", [])[:15], ensure_ascii=False, indent=2)
    weather_str = json.dumps(state.get("weather_data", []), ensure_ascii=False, indent=2)
    hotels_str = json.dumps(state.get("hotels_data", [])[:8], ensure_ascii=False, indent=2)

    retry_note = ""
    if retry > 0:
        retry_note = f"\n⚠️ 上次计划校验未通过，这是第 {retry} 次重试，请改进以下问题并确保 JSON 格式正确。"

    system_prompt = f"""你是顶级行程规划专家。根据以下真实数据生成 JSON 格式旅行计划。

# 景点数据（真实高德POI）:
{attrs_str}

# 天气数据:
{weather_str}

# 酒店数据:
{hotels_str}

# 用户需求:
- 城市: {state['city']}
- 日期: {state['start_date']} ~ {state['end_date']}
- 天数: {state['travel_days']} 天（必须恰好 {state['travel_days']} 天，不能多也不能少）
- 交通: {state['transportation']}
- 住宿: {state['accommodation']}
- 偏好: {state['preferences']}
- 额外要求: {state.get('free_text_input', '')}
{retry_note}

# ⚠️ 类型严格规则（必须遵守，否则返回数据无法解析）：

| 字段 | 类型 | 正确示例 | 错误示例 |
|------|------|----------|----------|
| accommodation | 字符串（必填） | "汕尾星河湾酒店" | {{"name":"酒店名"}}（不能是对象）|
| visit_duration | 整数（分钟） | 120 | "2小时", "1.5h" |
| ticket_price | 整数（元） | 60 | "60元", "免费", "待定" |
| hotel.rating | 字符串 | "4.5" | 4.5（不能是数字）|
| meals[].name | 字符串（必填） | "某某餐厅" | 缺失或用 restaurant 代替 |
| budget | 对象（不能是字符串） | {{"total":3000}} | "大约3000元左右" |

# 输出要求:
返回 JSON，包含 city/start_date/end_date/days/weather_info/overall_suggestions/budget。
days 中每天含 date/day_index/description/transportation/accommodation(字符串,当天住宿酒店名称)/hotel/attractions/meals。
景点含 name/address/location(经度纬度)/visit_duration/description/category/ticket_price。
weather_info 含 date/day_weather/night_weather/day_temp/night_temp/wind_direction/wind_power（温度纯数字）。
重要规则：
1. 景点必须来自上面真实数据，不得编造
2. 每天 2-3 个景点
3. 每天含早/中/晚三餐
4. 直接输出 JSON，不要用 ```json``` 包裹
"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请为{state['city']}生成{state['travel_days']}天旅行计划")
    ]
    response = llm.invoke(messages)
    plan_json = response.content.strip()

    # 清理可能的 markdown 包裹
    if plan_json.startswith("```"):
        plan_json = plan_json.split("\n", 1)[1] if "\n" in plan_json else plan_json[3:]
        if plan_json.endswith("```"):
            plan_json = plan_json[:-3]

    elapsed = time.time() - t0
    _log("LLM规划", f"LLM 返回完成 ✅ ({len(plan_json)} 字符, 耗时 {elapsed:.1f}s)")

    return {
        "final_plan_json": plan_json,
        "logs": [f"📋 行程规划生成 ({len(plan_json)} 字符, {elapsed:.0f}s)"],
    }


def validate_plan_node(state: TripState) -> dict:
    """计划校验节点 —— 检查 JSON 可解析性和内容完整性"""
    errors = []

    # 1. JSON 可解析性
    try:
        plan = json.loads(state["final_plan_json"])
    except json.JSONDecodeError as e:
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "logs": [f"❌ JSON 解析失败: {e}"],
        }

    # 2. 结构完整性
    if not plan.get("days"):
        errors.append("缺少 days 字段")
    if not plan.get("weather_info"):
        errors.append("缺少 weather_info 字段")
    if not plan.get("budget"):
        errors.append("缺少 budget 字段")

    days = plan.get("days", [])
    if len(days) != state["travel_days"]:
        errors.append(f"天数不匹配: 期望 {state['travel_days']}, 实际 {len(days)}")

    for d in days:
        if not d.get("attractions"):
            errors.append(f"第{d.get('day_index', '?')+1}天没有景点")
        if not d.get("meals"):
            errors.append(f"第{d.get('day_index', '?')+1}天没有餐饮")
        if not d.get("hotel"):
            errors.append(f"第{d.get('day_index', '?')+1}天没有酒店")

    settings = get_settings()
    if errors:
        new_count = state.get("retry_count", 0) + 1
        if new_count < settings.max_retries:
            _log("计划校验", f"⚠️ 校验失败 ({new_count}/{settings.max_retries}): {'; '.join(errors)}")
            _log("计划校验", "   ↻ 将重新规划...")
            return {
                "retry_count": new_count,
                "logs": [f"⚠️ 校验失败 (重试 {new_count}/{settings.max_retries}): {'; '.join(errors)}"],
            }
        else:
            _log("计划校验", f"⚠️ 已达最大重试次数，使用当前计划")
            return {
                "final_plan": plan,
                "logs": [f"⚠️ 校验未完全通过但已达最大重试，继续: {'; '.join(errors)}"],
            }

    _log("计划校验", f"✅ 校验通过: {len(days)}天, {sum(len(d.get('attractions',[])) for d in days)}个景点")
    return {
        "final_plan": plan,
        "logs": [f"✅ 校验通过"],
    }


def format_output_node(state: TripState) -> dict:
    """格式化输出节点"""
    plan = state.get("final_plan", {})
    days_count = len(plan.get("days", []))
    attractions_count = sum(len(d.get("attractions", [])) for d in plan.get("days", []))
    _log("格式化", f"✅ 最终计划: {state['city']}, {days_count}天, {attractions_count}个景点")
    if plan.get("budget") and isinstance(plan["budget"], dict):
        b = plan["budget"]
        _log("格式化", f"   💰 预算: 总 {b.get('total', '?')} 元")
    return {
        "logs": [f"✅ 最终计划: {state['city']}, {days_count}天, {attractions_count}个景点"],
    }


# ==================== 路由函数 ====================

def route_after_validate(state: TripState) -> str:
    """校验后路由：通过 → 格式化输出，失败 → 重新规划"""
    if state.get("final_plan"):
        return "format_output"
    return "plan_itinerary"


# ==================== 构建图 ====================

def build_trip_graph() -> StateGraph:
    """
    构建旅行规划 LangGraph 状态图

    流程:
        START → init
          ├─→ search_attractions (并行)
          ├─→ query_weather    (并行)
          └─→ search_hotels    (并行)
               ↓ (自动汇聚)
        plan_itinerary → validate_plan → 条件路由
          ↑                               ↓
          └── 失败重试 ─────────────────   format_output → END
    """
    graph = StateGraph(TripState)

    # 添加节点
    graph.add_node("init_state", init_state_node)
    graph.add_node("search_attractions", search_attractions_node)
    graph.add_node("query_weather", query_weather_node)
    graph.add_node("search_hotels", search_hotels_node)
    graph.add_node("plan_itinerary", plan_itinerary_node)
    graph.add_node("validate_plan", validate_plan_node)
    graph.add_node("format_output", format_output_node)

    # 边定义
    graph.add_edge(START, "init_state")

    # ★ 关键：三个搜索节点并行执行
    graph.add_edge("init_state", "search_attractions")
    graph.add_edge("init_state", "query_weather")
    graph.add_edge("init_state", "search_hotels")

    # 三个并行分支汇聚到规划节点
    graph.add_edge("search_attractions", "plan_itinerary")
    graph.add_edge("query_weather", "plan_itinerary")
    graph.add_edge("search_hotels", "plan_itinerary")

    # 规划 → 校验
    graph.add_edge("plan_itinerary", "validate_plan")

    # 条件路由：校验通过 → 格式化输出，否则 → 重新规划
    graph.add_conditional_edges(
        "validate_plan",
        route_after_validate,
        {"plan_itinerary": "plan_itinerary", "format_output": "format_output"}
    )

    graph.add_edge("format_output", END)

    return graph


# ==================== 图编译（单例） ====================

_graph = None


def get_compiled_graph():
    """获取编译好的 StateGraph（单例，带内存 checkpoint）"""
    global _graph
    if _graph is None:
        memory = MemorySaver()
        _graph = build_trip_graph().compile(checkpointer=memory)
        print("✅ LangGraph 状态图编译完成 (并行搜索 + 条件重试 + Checkpoint)")
    return _graph
