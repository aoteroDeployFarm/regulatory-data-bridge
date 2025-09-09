#!/usr/bin/env python3
"""
documents.py — FastAPI routes for querying and exporting documents.

Place at: app/routers/documents.py
Mount via: FastAPI(include_router(documents.router)).

What this does:
  - GET /documents
      Query documents with optional filters:
        • q (search text, matches title/text via ILIKE)
        • jurisdiction (e.g., CO)
        • date_from / date_to (ISO timestamps)
        • limit/offset (paginated)
      Returns list[DocumentOut] (pydantic schema).

  - GET /documents/export.csv
      Same filters as above, but streams CSV with:
        id, title, url, jurisdiction, published_at.

Why it matters:
  - Provides a clean API for browsing regulatory documents.
  - CSV export is useful for analysts, spreadsheets, reporting.

Common examples:
  curl "http://127.0.0.1:8000/documents?q=pipeline&jurisdiction=TX&limit=10"

  curl -L "http://127.0.0.1:8000/documents/export.csv?jurisdiction=CO&limit=100" -o CO_docs.csv
"""
from __future__ import annotations
from datetime import datetime
import csv, io

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.schemas import DocumentOut
from app.db.session import get_db
from app.db.crud import search_documents

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    q: str | None = None,
    jurisdiction: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Search documents with optional filters and pagination."""
    return search_documents(
        db,
        q=q,
        jurisdiction=jurisdiction,
        date_from=date_from,
        date_to=date_to,
        limit=min(limit, 200),
        offset=offset,
    )


@router.get("/export.csv")
def export_documents_csv(
    q: str | None = None,
    jurisdiction: str | None = None,
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Export filtered documents as CSV for download."""
    rows = search_documents(
        db,
        q=q,
        jurisdiction=jurisdiction,
        date_from=date_from,
        date_to=date_to,
        limit=min(limit, 5000),
        offset=offset,
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "url", "jurisdiction", "published_at"])
    for d in rows:
        w.writerow([d.id, d.title, d.url, d.jurisdiction or "", d.published_at or ""])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="documents.csv"'},
    )
