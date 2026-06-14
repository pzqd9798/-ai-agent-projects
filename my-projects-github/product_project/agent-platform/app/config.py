"""配置加载 — 从 .env 和环境变量读取所有配置项."""

import os
from pathlib import Path
from dataclasses import dataclass, field


# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_env():
    """加载 .env 文件，项目根目录的优先."""
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env", override=True)


_load_env()


@dataclass
class LLMConfig:
    model_id: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str | None = None

    @staticmethod
    def from_env() -> "LLMConfig":
        return LLMConfig(
            model_id=os.getenv("MODEL_ID", "claude-sonnet-4-6"),
            api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
        )


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000

    @staticmethod
    def from_env() -> "ServerConfig":
        return ServerConfig(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "8000")),
        )


@dataclass
class SessionConfig:
    session_dir: Path = field(default_factory=lambda: ROOT_DIR / "workspace" / ".sessions")
    context_safe_limit: int = 180000
    max_tool_output: int = 50000

    @staticmethod
    def from_env() -> "SessionConfig":
        return SessionConfig(
            session_dir=Path(os.getenv("SESSION_DIR", str(ROOT_DIR / "workspace" / ".sessions"))),
            context_safe_limit=int(os.getenv("CONTEXT_SAFE_LIMIT", "180000")),
            max_tool_output=int(os.getenv("MAX_TOOL_OUTPUT", "50000")),
        )


@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379"
    enabled: bool = True

    @staticmethod
    def from_env() -> "RedisConfig":
        url = os.getenv("REDIS_URL", "")
        return RedisConfig(
            url=url or "redis://localhost:6379",
            enabled=bool(url),
        )


@dataclass
class TelegramConfig:
    bot_token: str = ""
    enabled: bool = False

    @staticmethod
    def from_env() -> "TelegramConfig":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        return TelegramConfig(
            bot_token=token,
            enabled=bool(token),
        )


@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig.from_env)
    server: ServerConfig = field(default_factory=ServerConfig.from_env)
    session: SessionConfig = field(default_factory=SessionConfig.from_env)
    redis: RedisConfig = field(default_factory=RedisConfig.from_env)
    telegram: TelegramConfig = field(default_factory=TelegramConfig.from_env)


# 全局单例
config = AppConfig()
