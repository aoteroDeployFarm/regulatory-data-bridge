# services/web_api/settings.py
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    ENV: Literal["dev", "test", "prod"] = "dev"
    TIMEOUT_SECS: int = 15

    # reads env like RDB_TIMEOUT_SECS, and optional .env
    model_config = SettingsConfigDict(
        env_prefix="RDB_",
        env_file=".env",
        extra="ignore",
    )

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
