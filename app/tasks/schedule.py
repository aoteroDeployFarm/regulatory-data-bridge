#!/usr/bin/env python3
# app/tasks/schedule.py
"""
Background scheduler for periodic ingestion.

Uses APScheduler with a BackgroundScheduler to run ingestion jobs
in-process. This is suitable for small to medium deployments or dev/staging.
For production with multiple workers, consider a distributed scheduler (e.g., Celery beat).

Jobs:
  - `ingest_job`: Runs every 3 hours on the hour, calls run_ingest_once() with only_active=True.

Usage:
  from app.tasks.schedule import start_scheduler

  # inside FastAPI startup event:
  @app.on_event("startup")
  def startup_event():
      start_scheduler()

Notes:
  - Scheduler is idempotent: calling start_scheduler() multiple times returns the same instance.
  - DB sessions are managed per job via SessionLocal.
  - Timezone is fixed to UTC for predictable triggers.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.ingest import run_ingest_once

_scheduler: BackgroundScheduler | None = None


def _ingest_job() -> None:
    """Job wrapper: open DB session, run ingest, close DB."""
    db: Session = SessionLocal()
    try:
        run_ingest_once(db, only_active=True)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """
    Idempotently start the background scheduler.

    Returns:
        BackgroundScheduler: the singleton scheduler instance.
    """
    global _scheduler
    if _scheduler:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    # every 3 hours on the hour
    _scheduler.add_job(
        _ingest_job,
        "cron",
        minute=0,
        hour="*/3",
        id="ingest_job",
        replace_existing=True,
    )
    _scheduler.start()
    return _scheduler
