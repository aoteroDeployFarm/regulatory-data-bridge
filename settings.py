from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App
    app_name: str = "Regulatory Data Bridge"
    api_version: str = "0.1.0"
    environment: str = "local"  # local | dev | prod
    debug: bool = False
    log_level: str = "info"

    # Server defaults (used by scripts/compose, optional)
    host: str = "127.0.0.1"
    port: int = 8000

    # CORS (comma-separated in .env or JSON-style list)
    cors_origins: List[str] = ["*"]

    # Optional integrations / keys
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None  # for Gemini
    gemini_model: str = "models/gemini-1.5-pro"
    slack_webhook_url: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        # allow "https://a.com, https://b.com" or ["https://a.com", "https://b.com"]
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
