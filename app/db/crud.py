from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from .models import Source, Document, Alert

# --- Sources ---
def list_sources(db: Session, active: Optional[bool] = None):
    stmt = select(Source)
    if active is not None:
        stmt = stmt.where(Source.active == active)
    stmt = stmt.order_by(Source.name.asc())
    return db.execute(stmt).scalars().all()

def upsert_source(db: Session, *, name: str, url: str, jurisdiction: Optional[str], type_: str, active: bool = True):
    src = db.execute(select(Source).where(Source.name == name)).scalar_one_or_none()
    if src:
        src.url = url
        src.jurisdiction = jurisdiction
        src.type = type_
        src.active = active
        src.updated_at = datetime.utcnow()
        db.add(src); db.commit(); db.refresh(src)
        return src
    src = Source(name=name, url=url, jurisdiction=jurisdiction, type=type_, active=active)
    db.add(src); db.commit(); db.refresh(src)
    return src

# --- Documents ---
def create_or_update_doc(
    db: Session,
    *,
    source_id: int,
    title: str,
    url: str,
    published_at: Optional[datetime],
    text: Optional[str],
    metadata: Optional[dict],
    jurisdiction: Optional[str],
):
    existing = db.execute(select(Document).where(Document.url == url)).scalar_one_or_none()
    if existing:
        changed = False
        if title and existing.title != title:
            existing.title = title; changed = True
        if published_at and existing.published_at != published_at:
            existing.published_at = published_at; changed = True
        if text and (not existing.text):
            existing.text = text; changed = True
        if metadata and (not existing.meta):
            existing.meta = metadata; changed = True
        if jurisdiction and (existing.jurisdiction != jurisdiction):
            existing.jurisdiction = jurisdiction; changed = True
        if changed:
            db.add(existing); db.commit(); db.refresh(existing)
        return existing

    doc = Document(
        source_id=source_id,
        title=title or "(untitled)",
        url=url,
        published_at=published_at,
        text=text,
        meta=metadata,                # store in .meta
        jurisdiction=jurisdiction,
    )
    db.add(doc); db.commit(); db.refresh(doc)
    return doc

def search_documents(
    db: Session,
    *,
    q: Optional[str],
    jurisdiction: Optional[str],
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    limit: int = 50,
    offset: int = 0,
):
    stmt = select(Document).order_by(Document.published_at.desc().nullslast(), Document.id.desc())
    clauses = []
    if q:
        like = f"%{q}%"
        clauses.append(or_(Document.title.ilike(like), Document.text.ilike(like)))
    if jurisdiction:
        clauses.append(Document.jurisdiction == jurisdiction)
    if date_from:
        clauses.append(Document.published_at >= date_from)
    if date_to:
        clauses.append(Document.published_at <= date_to)
    if clauses:
        stmt = stmt.where(and_(*clauses))
    stmt = stmt.limit(limit).offset(offset)
    return db.execute(stmt).scalars().all()

# --- Alerts ---
def create_alert(db: Session, *, keyword: str, jurisdiction: Optional[str], active: bool = True):
    alert = Alert(keyword=keyword, jurisdiction=jurisdiction, active=active)
    db.add(alert); db.commit(); db.refresh(alert)
    return alert

def list_alerts(db: Session, *, active: Optional[bool] = None):
    stmt = select(Alert)
    if active is not None:
        stmt = stmt.where(Alert.active == active)
    return db.execute(stmt).scalars().all()
