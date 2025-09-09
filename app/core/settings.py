#!/usr/bin/env python3
"""
setting.py — Centralized, typed settings for the Regulatory Data Bridge.

Place at: app/setting.py
Run from the repo root (folder that contains app/).

What this does:
  - Loads configuration from environment variables and an optional .env file.
  - Provides strong typing + validation using Pydantic v2 (pydantic-settings).
  - Exposes a cached accessor get_settings() for easy DI (e.g., with FastAPI).

Highlights:
  - Environment-aware (development/staging/production)
  - Validates port ranges, SMTP port, chunk sizes/overlap, provider requirements
  - Auto-creates local files directory when STORAGE_PROVIDER=local
  - Optional providers: OpenAI/Gemini (LLM + embeddings), Slack, Expo/APNs/FCM
  - Database/Redis/Celery config, RAG params, and observability (Sentry)

Common examples:

  # 1) Import in FastAPI and inject once per request:
  from fastapi import Depends, FastAPI
  from app.setting import Settings, get_settings

  app = FastAPI()

  @app.get("/health")
  def health(cfg: Settings = Depends(get_settings)):
      return {"ok": True, "env": cfg.env, "llm": cfg.llm_provider}

  # 2) Override via env vars or .env file (see .env.example):
  export ENV=staging PORT=9000 LOG_LEVEL=DEBUG STORAGE_PROVIDER=local

Notes:
  - The .env file is loaded automatically if present (utf-8).
  - If STORAGE_PROVIDER=s3 or gcs, required provider fields must be set or validation will fail.
  - If LLM_PROVIDER=openai or gemini, corresponding API key must be set or validation will fail.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, HttpUrl, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------- Enums ----------

class AppEnv(str, Enum):
    development = "development"
    staging = "staging"
    production = "production"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LLMProvider(str, Enum):
    openai = "openai"
    gemini = "gemini"


class EmbeddingProvider(str, Enum):
    openai = "openai"
    gemini = "gemini"


class StorageProvider(str, Enum):
    local = "local"
    s3 = "s3"
    gcs = "gcs"


class PushProvider(str, Enum):
    expo = "expo"
    fcm = "fcm"
    apns = "apns"


# ---------- Settings ----------

class Settings(BaseSettings):
    # App
    app_name: str = Field("Regulatory Data Bridge", env="APP_NAME")
    env: AppEnv = Field(AppEnv.development, env="ENV")
    debug: bool = Field(False, env="DEBUG")
    log_level: LogLevel = Field(LogLevel.INFO, env="LOG_LEVEL")
    port: int = Field(8000, env="PORT")
    tz: str = Field("America/Denver", env="TZ")
    base_url: Optional[AnyHttpUrl] = Field(None, env="BASE_URL")

    # CORS
    cors_allowed_origins: List[str] = Field(default_factory=list, env="CORS_ALLOWED_ORIGINS")

    # API auth
    api_key: Optional[str] = Field(None, env="API_KEY")  # for X-API-Key flows
    secret_key: str = Field("change-me-please", env="SECRET_KEY")
    jwt_secret: str = Field("change-me-jwt", env="JWT_SECRET")

    # Database / Vector
    database_url: str = Field("postgresql+psycopg://reguser:regpass@localhost:5432/regdb", env="DATABASE_URL")
    pgvector_enabled: bool = Field(True, env="PGVECTOR_ENABLED")
    vector_table: str = Field("rag_chunks", env="VECTOR_TABLE")
    chunk_size_tokens: int = Field(1200, env="CHUNK_SIZE_TOKENS")
    chunk_overlap_chars: int = Field(800, env="CHUNK_OVERLAP_CHARS")

    # Cache / Queue
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    celery_broker_url: str = Field("redis://localhost:6379/1", env="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/2", env="CELERY_RESULT_BACKEND")

    # Model providers
    openai_api_key: Optional[str] = Field(None, env="OPENAI_API_KEY")
    gemini_api_key: Optional[str] = Field(None, env="GEMINI_API_KEY")

    llm_provider: LLMProvider = Field(LLMProvider.gemini, env="LLM_PROVIDER")
    llm_model: str = Field("gemini-1.5-pro", env="LLM_MODEL")

    embedding_provider: EmbeddingProvider = Field(EmbeddingProvider.openai, env="EMBEDDING_PROVIDER")
    openai_embedding_model: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    gemini_embedding_model: str = Field("text-embedding-004", env="GEMINI_EMBEDDING_MODEL")

    # Notifications
    slack_webhook_url: Optional[HttpUrl] = Field(None, env="SLACK_WEBHOOK_URL")
    slack_bot_token: Optional[str] = Field(None, env="SLACK_BOT_TOKEN")
    alert_channel: str = Field("#reg-updates", env="ALERT_CHANNEL")

    push_provider: PushProvider = Field(PushProvider.expo, env="PUSH_PROVIDER")
    expo_access_token: Optional[str] = Field(None, env="EXPO_ACCESS_TOKEN")
    fcm_server_key: Optional[str] = Field(None, env="FCM_SERVER_KEY")
    apns_team_id: Optional[str] = Field(None, env="APNS_TEAM_ID")
    apns_key_id: Optional[str] = Field(None, env="APNS_KEY_ID")
    apns_auth_key_path: Optional[str] = Field(None, env="APNS_AUTH_KEY_PATH")

    # Email
    smtp_host: Optional[str] = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_user: Optional[str] = Field(None, env="SMTP_USER")
    smtp_pass: Optional[str] = Field(None, env="SMTP_PASS")
    smtp_from: Optional[str] = Field(None, env="SMTP_FROM")

    # Storage
    storage_provider: StorageProvider = Field(StorageProvider.local, env="STORAGE_PROVIDER")
    files_dir: str = Field("./data/files", env="FILES_DIR")

    # AWS
    aws_region: Optional[str] = Field(None, env="AWS_REGION")
    aws_access_key_id: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = Field(None, env="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: Optional[str] = Field(None, env="AWS_S3_BUCKET")

    # GCP
    gcp_project_id: Optional[str] = Field(None, env="GCP_PROJECT_ID")
    gcp_credentials_json_path: Optional[str] = Field(None, env="GCP_CREDENTIALS_JSON_PATH")

    # Scrapers
    default_html_selector: str = Field("main, article, section, h1, h2, h3", env="DEFAULT_HTML_SELECTOR")
    http_timeout_seconds: int = Field(30, env="HTTP_TIMEOUT_SECONDS")
    user_agent: str = Field("RegDataBridge/1.0 (+https://example.com)", env="USER_AGENT")
    rate_limit_rpm: int = Field(60, env="RATE_LIMIT_RPM")
    rate_limit_burst: int = Field(10, env="RATE_LIMIT_BURST")
    proxy_url: Optional[str] = Field(None, env="PROXY_URL")

    # RAG / Q&A
    rag_top_k: int = Field(6, env="RAG_TOP_K")
    rag_min_score: float = Field(0.15, env="RAG_MIN_SCORE")

    # Observability
    sentry_dsn: Optional[HttpUrl] = Field(None, env="SENTRY_DSN")
    enable_sql_echo: bool = Field(False, env="ENABLE_SQL_ECHO")

    # GitHub Importer
    github_token: Optional[str] = Field(None, env="GITHUB_TOKEN")

    # Pydantic Settings config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- Validators ----------

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: str | List[str] | None) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [s.strip() for s in v if s and str(s).strip()]
        # comma-separated string
        return [s.strip() for s in str(v).split(",") if s.strip()]

    @field_validator("port")
    @classmethod
    def _port_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("PORT must be between 1 and 65535")
        return v

    @field_validator("chunk_size_tokens")
    @classmethod
    def _chunk_size_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("CHUNK_SIZE_TOKENS must be > 0")
        return v

    @field_validator("chunk_overlap_chars")
    @classmethod
    def _chunk_overlap_nonneg(cls, v: int, info: ValidationInfo) -> int:
        if v < 0:
            raise ValueError("CHUNK_OVERLAP_CHARS must be >= 0")
        return v

    @field_validator("llm_provider")
    @classmethod
    def _llm_requires_key(cls, v: LLMProvider, info: ValidationInfo) -> LLMProvider:
        data = info.data
        if v == LLMProvider.openai and not data.get("openai_api_key"):
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        if v == LLMProvider.gemini and not data.get("gemini_api_key"):
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        return v

    @field_validator("storage_provider")
    @classmethod
    def _storage_requires_config(cls, v: StorageProvider, info: ValidationInfo) -> StorageProvider:
        d = info.data
        if v == StorageProvider.local:
            # ensure directory exists (no heavy side-effects)
            p = Path(d.get("files_dir", "./data/files"))
            p.mkdir(parents=True, exist_ok=True)
        elif v == StorageProvider.s3:
            for key in ("aws_region", "aws_access_key_id", "aws_secret_access_key", "aws_s3_bucket"):
                if not d.get(key):
                    raise ValueError(f"{key.upper()} is required when STORAGE_PROVIDER=s3")
        elif v == StorageProvider.gcs:
            for key in ("gcp_project_id", "gcp_credentials_json_path"):
                if not d.get(key):
                    raise ValueError(f"{key.upper()} is required when STORAGE_PROVIDER=gcs")
        return v

    @field_validator("smtp_port")
    @classmethod
    def _smtp_port_range(cls, v: int) -> int:
        if not (1 <= v <= 65535):
            raise ValueError("SMTP_PORT must be between 1 and 65535")
        return v

    @property
    def is_prod(self) -> bool:
        return self.env == AppEnv.production

    @property
    def is_dev(self) -> bool:
        return self.env == AppEnv.development


# ---------- Accessor (cached) ----------

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached settings instance. Use as a FastAPI dependency:

        from fastapi import Depends, FastAPI
        from app.setting import get_settings

        app = FastAPI()

        @app.get("/health")
        def health(cfg: Settings = Depends(get_settings)):
            return {"env": cfg.env, "ok": True}
    """
    return Settings()
