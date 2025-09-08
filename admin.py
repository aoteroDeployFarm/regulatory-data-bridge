# app/routers/admin.py
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.db.crud import upsert_source as crud_upsert_source
from app.db.models import Document, Source
from app.db.session import get_db
from app.schemas import SourceCreate
from app.services.alerts import notify
from app.services.ingest import run_ingest_once

router = APIRouter(prefix="/admin", tags=["admin"])


# -----------------------------
# Ingest / Alerts
# -----------------------------
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


# -----------------------------
# Source admin
# -----------------------------
@router.post("/sources/toggle")
def toggle_source(
    name: str = Query(..., description="Exact source name"),
    active: bool = Query(...),
    db: Session = Depends(get_db),
):
    src = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail=f"Source not found: {name}")
    src.active = active
    db.add(src)
    db.commit()
    db.refresh(src)
    return {"ok": True, "name": src.name, "active": src.active}


@router.post("/sources/upsert")
def upsert_source_admin(payload: SourceCreate, db: Session = Depends(get_db)):
    """
    Create or update a source by (name, url).
    Active by default unless payload specifies otherwise.
    """
    src = crud_upsert_source(
        db,
        name=payload.name,
        url=payload.url,
        jurisdiction=payload.jurisdiction,
        type_=payload.type,
        active=payload.active,
    )
    return {"ok": True, "id": src.id, "name": src.name, "active": src.active}


# -----------------------------
# Cleanup helpers
# -----------------------------
@router.post("/cleanup/rrc-non-news")
def cleanup_rrc_non_news(db: Session = Depends(get_db)):
    """
    Delete Texas RRC rows that are not under /news/.
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


@router.post("/cleanup/by-url-pattern")
def cleanup_by_url_pattern(
    pattern: str = Query(..., description="Substring match (SQL LIKE '%pattern%')"),
    db: Session = Depends(get_db),
):
    """
    Delete documents whose URL contains `pattern`.
    Uses SQL LIKE, which is case-insensitive on SQLite and case-sensitive on Postgres.
    """
    # Safe for SQLite/Postgres
    res = db.execute(text("DELETE FROM documents WHERE url LIKE :pat"), {"pat": f"%{pattern}%"})
    db.commit()
    return {"deleted": res.rowcount, "pattern": pattern}


@router.post("/cleanup/non-http")
def cleanup_non_http(db: Session = Depends(get_db)):
    """
    Delete rows where URL does not start with http(s), e.g., mailto:, tel:, javascript:, or relative-only.
    """
    res = db.execute(text("DELETE FROM documents WHERE url NOT LIKE 'http%'"))
    db.commit()
    return {"deleted": res.rowcount}


@router.post("/cleanup/fragment-only")
def cleanup_fragment_only(db: Session = Depends(get_db)):
    """
    Delete rows where URL starts with a fragment (#...).
    """
    res = db.execute(text("DELETE FROM documents WHERE url LIKE '#%'"))
    db.commit()
    return {"deleted": res.rowcount}


@router.post("/cleanup/trailing-hash")
def cleanup_trailing_hash(db: Session = Depends(get_db)):
    """
    Delete rows where URL ends with a trailing '#'.
    """
    res = db.execute(text("DELETE FROM documents WHERE url LIKE '%#'"))
    db.commit()
    return {"deleted": res.rowcount}


@router.post("/cleanup/titles-exact")
def cleanup_titles_exact(
    title: str = Query(..., description="Exact title to remove"),
    db: Session = Depends(get_db),
):
    """
    Delete rows whose title exactly equals the given string (e.g., 'Home', 'Skip To Main Content').
    """
    res = db.execute(delete(Document).where(Document.title == title))
    db.commit()
    return {"deleted": res.rowcount, "title": title}
