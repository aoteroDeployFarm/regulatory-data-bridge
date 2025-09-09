#!/usr/bin/env python3
"""
crud.py — Database CRUD helpers for sources, documents, and alerts.

Place at: app/db/crud.py
Run from the repo root (folder that contains app/).

What this does:
  - Provides thin, typed helper functions around SQLAlchemy ORM for:
      • Sources: list, upsert
      • Documents: create-or-update, search with filters
      • Alerts: create, list
  - Keeps business logic minimal and side-effect predictable (commit/refresh inside ops).

Prereqs:
  - SQLAlchemy models defined in app/db/models.py (Source, Document, Alert).
  - A configured Session injected by the caller (e.g., FastAPI dependency).

Common examples:

  # List only active sources (sorted by name)
  from app.db.session import get_session
  from app.db import crud
  with get_session() as db:
      active_sources = crud.list_sources(db, active=True)

  # Upsert a source by name (idempotent)
  crud.upsert_source(
      db,
      name="CO – Health Department – Rules",
      url="https://example.gov/rules",
      jurisdiction="CO",
      type_="html",
      active=True,
  )

  # Create or update a document by URL
  crud.create_or_update_doc(
      db,
      source_id=1,
      title="New Rule Adopted",
      url="https://example.gov/rule-123",
      published_at=None,
      text="Full text...",
      metadata={"agency": "Health"},
      jurisdiction="CO",
  )

  # Search documents
  docs = crud.search_documents(
      db,
      q="air quality",
      jurisdiction="CO",
      date_from=None,
      date_to=None,
      limit=25,
      offset=0,
  )

  # Alerts
  crud.create_alert(db, keyword="PFAS", jurisdiction="CO", active=True)
  alerts = crud.list_alerts(db, active=True)
"""

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
