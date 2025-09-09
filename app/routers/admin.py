#!/usr/bin/env python3
"""
admin.py — FastAPI admin routes for ingestion, alerts, source toggling, and cleanup.

Place at: app/routers/admin.py
Mount via: FastAPI(include_router(admin.router)).

What this does:
  - POST /admin/ingest
      Run one-shot ingestion (calls app.services.ingest.run_ingest_once).
  - POST /admin/alerts/test?to=EMAIL
      Trigger test alert email (calls app.services.alerts.notify).
  - POST /admin/sources/toggle?name=...&active=true|false
      Toggle a source's active flag by name.
  - POST /admin/cleanup/rrc-non-news
      Delete TX Railroad Commission documents not under /news/.

Why it matters:
  - Provides operational knobs for developers/admins.
  - Simplifies manual testing, DB hygiene, and alert validation.

Security:
  - These routes are under /admin; protect them with API key or auth middleware.
  - Avoid exposing in production without access control.

Common examples:
  curl -X POST "http://127.0.0.1:8000/admin/ingest"
  curl -X POST "http://127.0.0.1:8000/admin/alerts/test?to=me@example.com"
  curl -X POST "http://127.0.0.1:8000/admin/sources/toggle?name=EPA&active=false"
  curl -X POST "http://127.0.0.1:8000/admin/cleanup/rrc-non-news"
"""

from __future__ import annotations
from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Source, Document
from app.services.ingest import run_ingest_once
from app.services.alerts import notify

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
def ingest(db: Session = Depends(get_db)):
    """Run a one-time ingest cycle."""
    try:
        stats = run_ingest_once(db)
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {type(e).__name__}: {e}")


@router.post("/alerts/test")
def alerts_test(to: str, db: Session = Depends(get_db)):
    """Send a test alert email to the given recipient."""
    try:
        notify(db, to_addr=to)
        return {"ok": True, "sent_to": to}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alerts failed: {type(e).__name__}: {e}")


@router.post("/sources/toggle")
def toggle_source(name: str = Query(...), active: bool = Query(...), db: Session = Depends(get_db)):
    """Toggle a Source.active flag by source name."""
    src = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source not found: {name}")
    src.active = active
    db.add(src); db.commit(); db.refresh(src)
    return {"ok": True, "name": src.name, "active": src.active}


@router.post("/cleanup/rrc-non-news")
def cleanup_rrc_non_news(db: Session = Depends(get_db)):
    """
    Delete TX Railroad Commission documents where:
      - jurisdiction == "TX"
      - URL host endswith "rrc.texas.gov"
      - path does NOT start with "/news/"
    """
    docs = db.execute(select(Document).where(Document.jurisdiction == "TX")).scalars().all()
    to_delete_ids = []
    for d in docs:
        try:
            u = urlparse(d.url)
        except Exception:
            continue
        if u.netloc.endswith("rrc.texas.gov") and not (u.path or "").startswith("/news/"):
            to_delete_ids.append(d.id)
    if to_delete_ids:
        db.execute(delete(Document).where(Document.id.in_(to_delete_ids)))
        db.commit()
    return {"deleted": len(to_delete_ids)}
