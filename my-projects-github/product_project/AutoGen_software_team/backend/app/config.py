"""配置管理 — 从 .env 和环境变量加载所有配置项."""

import os
from pathlib import Path
from dataclasses import dataclass, field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
WORKSPACE_DIR = ROOT_DIR / "workspace"


def _load_env():
    """加载 .env 文件."""
    from dotenv import load_dotenv
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)


_load_env()


@dataclass
class LLMConfig:
    """LLM 模型配置."""
    model_id: str = os.getenv("LLM_MODEL_ID", "deepseek-chat")
    api_key: str = os.getenv("LLM_API_KEY", "")
    base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    context_length: int = 8192


@dataclass
class DatabaseConfig:
    """数据库配置."""
    path: Path = WORKSPACE_DIR / "autogen_team.db"


@dataclass
class AuthConfig:
    """认证配置."""
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    jwt_algorithm: str = "HS256"
    token_expire_hours: int = 24


@dataclass
class SandboxConfig:
    """代码沙箱配置."""
    image: str = "python:3.11-slim"
    memory_limit: str = "256m"
    cpu_limit: float = 1.0
    timeout_seconds: int = 30
    network_disabled: bool = True


@dataclass
class RedisConfig:
    """Redis 配置."""
    url: str = os.getenv("REDIS_URL", "redis://localhost:6379")


@dataclass
class AppConfig:
    """应用配置."""
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "Coding Agent — 生产级软件研发平台"
    version: str = "2.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


@dataclass
class Config:
    """全局配置聚合."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    app: AppConfig = field(default_factory=AppConfig)

    # 工作目录
    artifacts_dir: Path = WORKSPACE_DIR / "artifacts"
    versions_dir: Path = WORKSPACE_DIR / "versions"
    logs_dir: Path = WORKSPACE_DIR / "logs"

    def __post_init__(self):
        for d in [self.artifacts_dir, self.versions_dir, self.logs_dir,
                  WORKSPACE_DIR]:
            d.mkdir(parents=True, exist_ok=True)


config = Config()
