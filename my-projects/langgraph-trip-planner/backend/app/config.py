"""配置管理模块 - 基于 Pydantic Settings"""
import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

# 尝试加载 HelloAgents 的 .env（兼容原有配置）
helloagents_env = Path(__file__).parent.parent.parent.parent.parent.parent / "HelloAgents" / ".env"
if helloagents_env.exists():
    load_dotenv(helloagents_env, override=False)


class Settings(BaseSettings):
    """应用配置"""

    # 应用基本配置
    app_name: str = "HelloAgents智能旅行助手 (LangGraph版)"
    app_version: str = "2.0.0-langgraph"
    debug: bool = False

    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"

    # 高德地图 API
    amap_api_key: str = ""

    # Unsplash API
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""

    # LLM 配置（兼容 HelloAgents 变量名 LLM_API_KEY / LLM_MODEL_ID / LLM_BASE_URL）
    openai_api_key: str = Field(
        default="",
        validation_alias="LLM_API_KEY",
        description="LLM API Key (OpenAI/DeepSeek 等)"
    )
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="LLM_BASE_URL",
        description="LLM API Base URL"
    )
    openai_model: str = Field(
        default="gpt-4o",
        validation_alias="LLM_MODEL_ID",
        description="LLM 模型名称"
    )

    # LangGraph 配置
    max_retries: int = 2  # 计划校验不通过时的最大重试次数
    search_timeout: int = 30  # 搜索超时（秒）

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

    def get_cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


# 全局单例
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def validate_config():
    """验证必要配置"""
    s = get_settings()
    errors = []
    if not s.amap_api_key:
        errors.append("AMAP_API_KEY 未配置")
    if not s.openai_api_key:
        errors.append("LLM_API_KEY 未配置 (LLM)")
    if errors:
        raise ValueError("\n".join(errors))
    print("✅ 配置验证通过 (图片服务: 高德 POI 内置)")


def print_config():
    """打印当前配置（脱敏）"""
    s = get_settings()
    mask = lambda v: v[:4] + "****" + v[-4:] if v and len(v) > 8 else "****"
    print(f"  高德 API Key: {mask(s.amap_api_key)}")
    print(f"  LLM Model: {s.openai_model}")
    print(f"  LLM Base URL: {s.openai_base_url}")
    print(f"  LangGraph Max Retries: {s.max_retries}")
