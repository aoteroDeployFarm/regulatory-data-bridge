#!/usr/bin/env python3
"""
alerts.py — FastAPI routes for creating and listing alerts.

Place at: app/routers/alerts.py
Mount via: FastAPI(include_router(alerts.router)).

What this does:
  - GET /alerts
      List alerts. Optional query param `active=true|false` to filter.
  - POST /alerts
      Create a new alert (keyword + jurisdiction + active flag).

Why it matters:
  - Exposes alert management endpoints to the API.
  - Alerts can later be tied to notification delivery (email, Slack, push).

Models:
  - AlertCreate (pydantic) → request body for POST.
  - AlertOut (pydantic) → response model for GET/POST.

DB helpers:
  - Uses app.db.crud.create_alert() and list_alerts().

Common examples:
  curl "http://127.0.0.1:8000/alerts?active=true"
      # list active alerts

  curl -X POST "http://127.0.0.1:8000/alerts" \
       -H "Content-Type: application/json" \
       -d '{"keyword":"pipeline","jurisdiction":"CO","active":true}'
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..schemas import AlertCreate, AlertOut
from ..db.session import get_db
from ..db.crud import create_alert, list_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def get_alerts(active: bool | None = None, db: Session = Depends(get_db)):
    """List alerts, optionally filtered by active flag."""
    return list_alerts(db, active=active)


@router.post("", response_model=AlertOut)
def new_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    """Create a new alert record."""
    return create_alert(
        db,
        keyword=payload.keyword,
        jurisdiction=payload.jurisdiction,
        active=payload.active,
    )
