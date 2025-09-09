#!/usr/bin/env python3
"""
sources.py — FastAPI routes for managing regulatory sources.

Place at: app/routers/sources.py
Mount via: FastAPI(include_router(sources.router)).

What this does:
  - GET  /sources
      List sources, optionally filtered by active flag.
  - POST /sources
      Upsert (insert or update) a source by unique name.

Why it matters:
  - Provides CRUD API endpoints to manage regulatory source metadata.
  - Used by ingestion jobs and admin tools to control which sources are active.

Schemas:
  - SourceCreate → input payload (name, url, jurisdiction, type, active).
  - SourceOut    → response model for a Source.

Dependencies:
  - get_db (SQLAlchemy session)
  - app.db.crud for persistence.

Common examples:
  curl "http://127.0.0.1:8000/sources"
  curl -X POST "http://127.0.0.1:8000/sources" \
       -H "Content-Type: application/json" \
       -d '{"name":"Texas RRC","url":"https://rrc.texas.gov/news","jurisdiction":"TX","type":"html","active":true}'
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..schemas import SourceCreate, SourceOut
from ..db.session import get_db
from ..db import crud

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceOut])
def list_sources(active: bool | None = None, db: Session = Depends(get_db)):
    """List sources, optionally filtered by active flag."""
    return crud.list_sources(db, active=active)


@router.post("", response_model=SourceOut)
def upsert_source(payload: SourceCreate, db: Session = Depends(get_db)):
    """Insert or update a source (idempotent by unique name)."""
    src = crud.upsert_source(
        db,
        name=payload.name,
        url=payload.url,
        jurisdiction=payload.jurisdiction,
        type_=payload.type,
        active=payload.active,
    )
    return src
