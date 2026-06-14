"""配置管理 — 从环境变量 /.env 加载."""

import os
from pathlib import Path
from dataclasses import dataclass, field

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_dotenv() -> None:
    if ENV_FILE.exists():
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key, val = key.strip(), val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val


_load_dotenv()


# ---------------------------------------------------------------------------
# 应用配置
# ---------------------------------------------------------------------------

@dataclass
class AppConfig:
    title: str = "RAG Agent Pro"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    def __post_init__(self):
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.port = int(os.getenv("PORT", str(self.port)))


# ---------------------------------------------------------------------------
# LLM 配置
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = ""
    model_id: str = "claude-sonnet-4-6"
    embedding_model: str = "voyage-3"  # Anthropic Voyage embedding
    max_tokens: int = 4096

    def __post_init__(self):
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "")
        self.model_id = os.getenv("MODEL_ID", self.model_id)
        self.embedding_model = os.getenv("EMBEDDING_MODEL", self.embedding_model)


# ---------------------------------------------------------------------------
# 基础设施配置
# ---------------------------------------------------------------------------

@dataclass
class InfraConfig:
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours
    redis_url: str = "redis://localhost:6379"
    database_url: str = ""

    def __post_init__(self):
        self.jwt_secret = os.getenv("JWT_SECRET", self.jwt_secret)
        self.redis_url = os.getenv("REDIS_URL", self.redis_url)
        db_dir = Path(__file__).resolve().parent.parent.parent / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.database_url = os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{db_dir / 'rag_agent.db'}",
        )


# ---------------------------------------------------------------------------
# 检索配置
# ---------------------------------------------------------------------------

@dataclass
class RetrievalConfig:
    top_k: int = 5
    chunk_size: int = 800
    chunk_overlap: int = 100
    hybrid_alpha: float = 0.7  # 0=纯关键词, 1=纯向量
    max_context_tokens: int = 8000
    rerank_enabled: bool = True


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

config = AppConfig()
llm = LLMConfig()
infra = InfraConfig()
retrieval = RetrievalConfig()
