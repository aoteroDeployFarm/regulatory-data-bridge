# app/routers/documents.py
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
