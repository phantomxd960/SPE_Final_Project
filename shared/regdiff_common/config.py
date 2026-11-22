"""Runtime configuration, read from environment variables.

Secrets (database password, JWT secret, LLM key) arrive as environment
variables too: from `.env` locally, from a Kubernetes Secret, or from files
that the Vault agent renders and the container entrypoint sources.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", protected_namespaces=("settings_",))

    # Identity of the running build (shown in the dashboard footer, UI-6)
    service_name: str = "regulationdiff"
    build_number: str = "dev"
    git_commit: str = "local"
    build_time: str = "unknown"

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "regulationdiff"
    db_user: str = "regulationdiff"
    db_password: str = "regulationdiff"
    database_url: str | None = None  # overrides the db_* fields when set

    # Auth
    jwt_secret: str = "change-me"
    jwt_expiry_minutes: int = 480
    admin_email: str = "admin@regulationdiff.local"
    admin_password: str = "admin123"

    # Storage and uploads
    storage_dir: str = "./data/documents"
    max_upload_mb: int = 10

    # AI
    llm_mode: Literal["mock", "openai", "gemini"] = "mock"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_timeout_seconds: float = 60.0
    embeddings_mode: Literal["mock", "fastembed"] = "mock"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    model_cache_dir: str = "./data/models"

    # Analysis thresholds (Section 8, tuned on the labelled set)
    align_min_similarity: float = 0.60
    renumbered_min_similarity: float = 0.95
    equivalent_min_embedding_similarity: float = 0.92
    equivalent_max_word_overlap: float = 0.70
    graph_inferred_threshold: float = 0.75
    graph_max_depth: int = 3
    retrieval_candidates: int = 10
    retrieval_top_k: int = 5

    # Worker
    worker_poll_seconds: float = 2.0
    worker_max_attempts: int = 3
    worker_health_port: int = 8001

    log_level: str = "INFO"

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        credentials = f"{self.db_user}:{self.db_password}"
        return f"postgresql+psycopg://{credentials}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
