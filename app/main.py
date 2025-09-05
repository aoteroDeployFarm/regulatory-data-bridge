from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import Settings, get_settings

# ---------- Lifespan: logging + timezone ----------
def _configure_logging(cfg: Settings) -> None:
    level_name = cfg.log_level.value if hasattr(cfg.log_level, "value") else str(cfg.log_level)
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("uvicorn.access").setLevel(logging.INFO if cfg.debug else logging.WARNING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()
    # Timezone
    os.environ["TZ"] = cfg.tz
    try:
        time.tzset()  # not available on Windows
    except Exception:
        pass

    # Logging
    _configure_logging(cfg)
    logging.getLogger("regbridge").info(
        "app_start",
        extra={"env": cfg.env, "model": cfg.llm_model, "provider": cfg.llm_provider},
    )
    yield
    logging.getLogger("regbridge").info("app_stop")

# We intentionally defer cfg access until after settings are ready.
app = FastAPI(
    title="Regulatory Data Bridge",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS (add immediately; settings will be read now — make sure your .env has valid keys)
_cfg = get_settings()
allowed_origins = _cfg.cors_allowed_origins
# In dev, allow all if no explicit origins were set
if _cfg.env == _cfg.env.development and not allowed_origins:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Routers ----------
from app.routers import ask, updates, process, notifications  # noqa: E402

app.include_router(ask.router)
app.include_router(updates.router)
app.include_router(process.router)
app.include_router(notifications.router)

# ---------- Health ----------
@app.get("/health")
def health(cfg: Settings = Depends(get_settings)):
    return {
        "ok": True,
        "name": cfg.app_name,
        "env": cfg.env,
        "tz": cfg.tz,
        "time": datetime.now(timezone.utc).isoformat(),
        "vector": cfg.pgvector_enabled,
        "provider": cfg.llm_provider,
        "model": cfg.llm_model,
    }
