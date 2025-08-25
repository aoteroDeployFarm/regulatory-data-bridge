# services/web_api/app.py
from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .settings import get_settings
from .registry import discover
from .routes import updates, metrics
from shared.logging import setup_json_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_json_logging()
    settings = get_settings()
    app.state.settings = settings
    app.state.scraper_map = discover()  # build registry once at startup
    app.state.metrics = {"runs": 0, "updates": 0, "errors": 0}
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Regulatory Data Bridge API", version="0.1.0", lifespan=lifespan)
    app.include_router(updates.router)
    app.include_router(metrics.router)

    @app.get("/health")
    def health():
        return {
            "ok": True,
            "env": app.state.settings.ENV,
            "scrapers": len(app.state.scraper_map),
        }

    return app
