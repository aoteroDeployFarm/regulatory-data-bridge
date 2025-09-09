#!/usr/bin/env python3
"""
updates.py — FastAPI routes for listing processed regulatory updates.

Place at: app/routers/updates.py
Mount via: FastAPI(include_router(updates.router)).

What this does:
  - GET /updates
      Returns a list of processed regulatory updates (stub for now).
      Supports filters for jurisdiction, class, date, and risk score.

Why it matters:
  - Intended for frontends that show end-users the most recent regulatory changes.
  - Will eventually be backed by DB queries and AI-generated summaries/risk scoring.

Schemas:
  - UpdateMeta → metadata about the update (class, jurisdiction, agency, fetched_at).
  - UpdateItem → top-level update object (id, url, summary_short, risk_score, entities, meta).

Current status:
  - Returns a static demo item until DB and processing pipeline are integrated.

Common example:
  curl "http://127.0.0.1:8000/updates?jurisdiction=CO&risk_min=30&limit=10"
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from settings import Settings, get_settings

router = APIRouter(prefix="/updates", tags=["updates"])


class UpdateMeta(BaseModel):
    doc_class: Optional[str] = None
    jurisdiction: Optional[str] = None
    agency: Optional[str] = None
    fetched_at: Optional[str] = None


class UpdateItem(BaseModel):
    id: str
    url: str
    summary_short: Optional[str] = None
    risk_score: Optional[int] = Field(None, ge=0, le=100)
    entities: List[dict] = Field(default_factory=list)
    meta: UpdateMeta


@router.get("", response_model=List[UpdateItem])
def list_updates(
    jurisdiction: Optional[str] = None,
    klass: Optional[str] = Query(None, alias="class"),
    since: Optional[str] = None,
    risk_min: Optional[int] = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=200),
    cfg: Settings = Depends(get_settings),
) -> List[UpdateItem]:
    """
    List processed updates (stub implementation).
    TODO: Replace with DB query and AI outputs.
    """
    item = UpdateItem(
        id="demo-1",
        url="https://example.gov/notice/abc",
        summary_short="Demo summary (replace with AI output).",
        risk_score=37,
        entities=[{"type": "agency", "value": "Example Agency"}],
        meta=UpdateMeta(
            doc_class="Technical guidance",
            jurisdiction=jurisdiction or "CO",
            agency="EXA",
            fetched_at="2025-09-05T12:00:00Z",
        ),
    )
    return [item]
