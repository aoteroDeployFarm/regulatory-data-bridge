# app/schemas.py
"""
Pydantic schemas for API input/output.

Covers:
  - Sources (create, output)
  - Documents (output, query)
  - Alerts (create, output)

Notes:
  - Uses `from_attributes = True` for ORM → Pydantic conversion.
  - `DocumentOut.metadata` maps from ORM field `meta`.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, AliasChoices

# ----------------------------
# Sources
# ----------------------------

class SourceCreate(BaseModel):
    name: str
    url: str
    jurisdiction: Optional[str] = None  # e.g., "US", "TX", "CA"
    type: str = Field(default="rss", pattern="^(rss|html)$")
    active: bool = True


class SourceOut(SourceCreate):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ----------------------------
# Documents
# ----------------------------

class DocumentOut(BaseModel):
    id: int
    source_id: int
    title: str
    url: str
    published_at: Optional[datetime] = None
    text: Optional[str] = None

    # Read from ORM attribute `meta`, but serialize as `metadata`
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("meta", "metadata"),
    )

    jurisdiction: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentQuery(BaseModel):
    q: Optional[str] = None
    jurisdiction: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


# ----------------------------
# Alerts
# ----------------------------

class AlertCreate(BaseModel):
    keyword: str
    jurisdiction: Optional[str] = None
    active: bool = True


class AlertOut(AlertCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
