from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from settings import Settings, get_settings

router = APIRouter(prefix="/process", tags=["ai"])

class ProcessResult(BaseModel):
    ok: bool
    update_id: str
    summary_short: str | None = None
    risk_score: int | None = None

@router.post("/{update_id}", response_model=ProcessResult)
def process_update(
    update_id: str = Path(..., min_length=1),
    cfg: Settings = Depends(get_settings),
) -> ProcessResult:
    # TODO: run summarize/classify/entities and persist
    return ProcessResult(ok=True, update_id=update_id, summary_short=None, risk_score=None)
