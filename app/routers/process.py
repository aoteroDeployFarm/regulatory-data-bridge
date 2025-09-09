#!/usr/bin/env python3
"""
process.py — FastAPI routes for AI post-processing of regulatory updates.

Place at: app/routers/process.py
Mount via: FastAPI(include_router(process.router)).

What this does:
  - POST /process/{update_id}
      Runs AI-powered processing on a regulatory update (summarization,
      classification, risk scoring, entity extraction, etc.).

Why it matters:
  - Provides a structured way to enrich ingested updates with summaries and risk signals.
  - Downstream clients (dashboards, alerts, reports) will consume these enriched fields.

Models:
  - ProcessResult → response containing status, update_id, optional summary and risk score.

Dependencies:
  - Depends(get_settings) for configuration and future LLM provider selection.

Common examples:
  curl -X POST "http://127.0.0.1:8000/process/abc123" \
       -H "Content-Type: application/json"
      # → {"ok": true, "update_id": "abc123", "summary_short": null, "risk_score": null}

Notes:
  - Currently returns a placeholder; real implementation should call summarizer/classifier
    and persist results in the database.
"""
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
    """
    Run AI post-processing for a regulatory update (placeholder).
    TODO: wire in summarization, classification, risk scoring, persistence.
    """
    return ProcessResult(ok=True, update_id=update_id, summary_short=None, risk_score=None)
