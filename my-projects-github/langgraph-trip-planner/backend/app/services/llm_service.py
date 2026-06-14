"""LLM 服务模块 - 基于 LangChain ChatOpenAI"""
from langchain_openai import ChatOpenAI
from ..config import get_settings

_llm: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    """获取 LangChain ChatOpenAI 实例（单例）"""
    global _llm
    if _llm is None:
        settings = get_settings()
        _llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        print(f"✅ LLM 服务初始化: {settings.openai_model}")
    return _llm


def reset_llm():
    global _llm
    _llm = None
