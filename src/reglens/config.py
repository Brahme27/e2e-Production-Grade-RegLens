"""Central configuration: typed settings from environment variables / .env (prefix REGLENS_)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REGLENS_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Literal["local", "dev", "prod", "test"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_json: bool = False
    random_seed: int = 42

    # folders
    data_dir: Path = Field(default=PROJECT_ROOT / "data")
    artifacts_dir: Path = Field(default=PROJECT_ROOT / "artifacts")
    configs_dir: Path = Field(default=PROJECT_ROOT / "configs")
    evals_dir: Path = Field(default=PROJECT_ROOT / "evals")
    llm_config_path: Path = Field(default=PROJECT_ROOT / "configs" / "litellm.yaml")
    # every LLM answer is cached here (committed, so evals and CI replay without a key)
    llm_cache_dir: Path = Field(default=PROJECT_ROOT / "cache" / "llm")

    # storage: local files by default, real services in docker compose / cloud
    database_url: str | None = None  # None -> SQLite file under artifacts/
    qdrant_url: str | None = None  # None -> embedded Qdrant under artifacts/qdrant
    qdrant_collection: str = "reglens"
    redis_url: str | None = None  # None -> in-process semantic cache

    # crawling (polite by default)
    crawl_user_agent: str = "RegLens-research/0.1 (+https://github.com/Brahme27/reglens)"
    crawl_delay_seconds: float = 1.5
    crawl_timeout_seconds: float = 60.0

    # retrieval models (local ONNX on CPU, downloaded once)
    dense_model: str = "BAAI/bge-small-en-v1.5"
    sparse_model: str = "Qdrant/bm25"
    rerank_model: str = "BAAI/bge-reranker-v2-m3-int8"
    models_cache_dir: Path | None = Field(default=PROJECT_ROOT / ".cache" / "fastembed")
    # which index variant the alias "reglens" serves: E1 won the ablation (E2 summaries hurt)
    serving_variant: str = "para_ctx"

    # secrets
    groq_api_key: SecretStr | None = None
    api_key: SecretStr | None = None  # when set, /v1 endpoints need header X-API-Key
    rate_limit_per_minute: int = 30  # /v1/ask per client (API key or IP)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def reports_dir(self) -> Path:
        return self.artifacts_dir / "reports"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def sqlalchemy_url(self) -> str:
        return self.database_url or f"sqlite:///{(self.artifacts_dir / 'reglens.db').as_posix()}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
