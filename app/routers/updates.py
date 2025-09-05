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
    # TODO: query DB; return newest first
    # Placeholder stub
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
