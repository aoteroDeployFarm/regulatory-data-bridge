# app/main.py
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import sources, documents, alerts, admin

app = FastAPI(title="Regulatory Data Bridge", version="0.1.0")

# CORS (MVP: allow all; tighten later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def get_health():
    return {"status": "ok"}

# Routers
app.include_router(sources.router)
app.include_router(documents.router)
app.include_router(alerts.router)
app.include_router(admin.router)

# Scheduler (toggle with env START_SCHEDULER=1)
if os.getenv("START_SCHEDULER", "1") == "1":
    try:
        from app.tasks.schedule import start_scheduler
        @app.on_event("startup")
        def _start_jobs():
            start_scheduler()
    except Exception as e:
        # Don't kill the server if scheduler fails; log and continue
        print(f"[scheduler] disabled due to error: {e}")
