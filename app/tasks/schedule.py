# app/tasks/schedule.py
from __future__ import annotations
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.ingest import run_ingest_once

_scheduler: BackgroundScheduler | None = None

def _ingest_job():
    db: Session = SessionLocal()
    try:
        run_ingest_once(db, only_active=True)
    finally:
        db.close()

def start_scheduler() -> BackgroundScheduler:
    """Idempotently start the background scheduler."""
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    # every 3 hours on the hour
    _scheduler.add_job(_ingest_job, "cron", minute=0, hour="*/3", id="ingest_job", replace_existing=True)
    _scheduler.start()
    return _scheduler
