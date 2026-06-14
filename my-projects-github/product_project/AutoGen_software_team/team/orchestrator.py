"""团队编排 — 创建团队、配置模型、执行任务并记录输出."""

import os
import json
from pathlib import Path
from datetime import datetime

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console

from .agents import (
    create_product_manager,
    create_engineer,
    create_code_reviewer,
    create_user_proxy,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


# ---------------------------------------------------------------------------
# 模型工厂
# ---------------------------------------------------------------------------

def create_model_client() -> OpenAIChatCompletionClient:
    """根据环境变量创建 LLM 客户端，支持 OpenAI 兼容接口."""
    return OpenAIChatCompletionClient(
        model=os.getenv("LLM_MODEL_ID", "deepseek-chat"),
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=False,
            family="unknown",
            context_length=8192,
        ),
    )


# ---------------------------------------------------------------------------
# 任务库
# ---------------------------------------------------------------------------

PRESET_TASKS = {
    "bitcoin-tracker": """开发一个比特币价格追踪应用。

核心功能：
- 实时显示比特币当前价格（USD）
- 显示 24 小时价格变化趋势（涨跌幅和涨跌额）
- 提供价格刷新功能

技术要求：
- 使用 Streamlit 框架
- 界面简洁美观
- 添加错误处理和加载状态""",

    "todo-api": """设计并实现一个 RESTful Todo API 服务。

核心功能：
- 创建、读取、更新、删除（CRUD）待办事项
- 支持按状态筛选（已完成/未完成）
- 数据持久化（SQLite）

技术要求：
- 使用 FastAPI 框架
- Pydantic 数据模型
- 完整的 API 文档（自动生成 Swagger）
- 包含单元测试""",

    "markdown-blog": """开发一个 Markdown 个人博客系统。

核心功能：
- 支持 Markdown 文件渲染为网页
- 文章列表和分类标签
- 代码语法高亮
- 响应式设计

技术要求：
- 使用 Flask 框架
- 支持 front-matter 元数据
- 简洁优雅的默认主题""",
}


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

async def run_team(task: str, max_turns: int = 20) -> dict:
    """运行完整的软件开发团队协作流程.

    Args:
        task: 自然语言任务描述
        max_turns: 最大对话轮次

    Returns:
        {"task": str, "messages": list, "output_file": str}
    """
    model_client = create_model_client()

    # 创建团队
    team = RoundRobinGroupChat(
        participants=[
            create_product_manager(model_client),
            create_engineer(model_client),
            create_code_reviewer(model_client),
            create_user_proxy(),
        ],
        termination_condition=TextMentionTermination("TERMINATE"),
        max_turns=max_turns,
    )

    # 记录开始
    print(f"\n{'='*60}")
    print(f"  🤖 AutoGen 软件研发团队 — 开始协作")
    print(f"  📋 任务: {task[:80]}...")
    print(f"{'='*60}\n")

    # 运行并展示对话
    result = await Console(team.run_stream(task=task))

    # 保存输出
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"session_{timestamp}.md"

    # 生成 Markdown 记录
    md_lines = [
        f"# AutoGen 软件研发团队 — 协作记录",
        f"",
        f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**任务**: {task}",
        f"**角色**: ProductManager → Engineer → CodeReviewer → UserProxy",
        f"",
        f"---",
        f"",
    ]

    # 提取对话消息
    if hasattr(result, "messages") and result.messages:
        md_lines.append("## 对话记录")
        md_lines.append("")
        for msg in result.messages:
            role = getattr(msg, "source", "unknown")
            content = getattr(msg, "content", str(msg))
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            md_lines.append(f"### {role}")
            md_lines.append("")
            md_lines.append(str(content)[:5000])
            md_lines.append("")
            md_lines.append("---")
            md_lines.append("")

    output_file.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  ✅ 协作完成")
    print(f"  💾 记录已保存: {output_file}")
    print(f"{'='*60}\n")

    return {
        "task": task,
        "output_file": str(output_file),
    }
