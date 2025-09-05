# app/main.py
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from settings import Settings, get_settings  # root-level settings.py


def create_app(cfg: Settings) -> FastAPI:
    app = FastAPI(
        title=cfg.app_name,
        version=cfg.api_version,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS (compatible with old 'cors_allowed_origins' and new 'cors_origins')
    allowed_origins = getattr(cfg, "cors_allowed_origins", None) or cfg.cors_origins or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers (include if present; don't crash if some aren't there yet)
    try:
        from app.routers import ask  # type: ignore
        app.include_router(ask.router)
    except Exception:
        pass

    try:
        from app.routers import updates  # type: ignore
        app.include_router(updates.router)
    except Exception:
        pass

    try:
        from app.routers import process  # type: ignore
        app.include_router(process.router)
    except Exception:
        pass

    try:
        from app.routers import notifications  # type: ignore
        app.include_router(notifications.router)
    except Exception:
        pass

    try:
        from app.routers import admin  # type: ignore
        app.include_router(admin.router)
    except Exception:
        pass

    # Meta endpoints
    @app.get("/", tags=["meta"])
    def root(settings: Settings = Depends(get_settings)):
        return {
            "name": settings.app_name,
            "version": settings.api_version,
            "env": settings.environment,
            "time": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {"ok": True, "ts": datetime.now(timezone.utc).isoformat()}

    return app


# ASGI app
app = create_app(get_settings())
