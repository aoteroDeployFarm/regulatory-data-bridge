# app/routers/admin.py
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
    try:
        stats = run_ingest_once(db)
        return {"ok": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {type(e).__name__}: {e}")

@router.post("/alerts/test")
def alerts_test(to: str, db: Session = Depends(get_db)):
    try:
        notify(db, to_addr=to)
        return {"ok": True, "sent_to": to}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Alerts failed: {type(e).__name__}: {e}")

@router.post("/sources/toggle")
def toggle_source(name: str = Query(...), active: bool = Query(...), db: Session = Depends(get_db)):
    src = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source not found: {name}")
    src.active = active
    db.add(src); db.commit(); db.refresh(src)
    return {"ok": True, "name": src.name, "active": src.active}

@router.post("/cleanup/rrc-non-news")
def cleanup_rrc_non_news(db: Session = Depends(get_db)):
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
