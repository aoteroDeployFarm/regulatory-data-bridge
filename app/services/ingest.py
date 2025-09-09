#!/usr/bin/env python3
"""
ingest.py — One-shot ingestion runner for all configured sources.

Place at: app/services/ingest.py  (current imports expect app.services.ingest or app.services used by routers)
Run from: invoked by API route /admin/ingest, admin scripts, or tests.

What this does:
  - Loads Source rows (optionally only active ones).
  - For each source, dispatches to the correct scraper:
      • type == "rss"  → app.scrapers.rss.run_rss
      • type == "html" → app.scrapers.html.run_html
  - Captures per-source success/error and returns an aggregate stats dict.

Why it matters:
  - Central control point for ingestion—keeps routers/CLIs thin.
  - Uniform success/error accounting useful for logs, dashboards, and tests.

Return shape (example):
  {
    "total": 3,
    "ok": 2,
    "errors": 1,
    "per_source": [
      {"source": "EPA – News Releases (RSS)", "type": "rss", "url": "...", "ok": True,  "error": None},
      {"source": "Texas RRC – News (HTML)",   "type": "html","url": "...", "ok": True,  "error": None},
      {"source": "Some Bad Source",           "type": "rss", "url": "...", "ok": False, "error": "ValueError: ..."}
    ]
  }

Common examples (pseudo):
  from app.db.session import get_session
  from app.services.ingest import run_ingest_once

  with get_session() as db:
      stats = run_ingest_once(db, only_active=True)
      print(stats)

Notes:
  - Unsupported source types raise ValueError but are captured per-source in results.
  - DB session is provided by caller; this function does not commit/rollback itself.
"""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Source
from app.scrapers.rss import run_rss
from app.scrapers.html import run_html


def run_ingest_once(db: Session, only_active: bool = True) -> dict:
    """
    Iterate all sources (optionally only active) and run their respective scrapers.

    Args:
        db: SQLAlchemy Session.
        only_active: If True, limit to Source.active == True.

    Returns:
        Stats dictionary (see module docstring for shape).
    """
    q = select(Source)
    if only_active:
        q = q.where(Source.active == True)  # noqa: E712
    sources = db.execute(q).scalars().all()

    stats: Dict[str, Any] = {"total": len(sources), "ok": 0, "errors": 0, "per_source": []}
    for src in sources:
        entry = {"source": src.name, "type": src.type, "url": src.url, "ok": False, "error": None}
        try:
            if src.type == "rss":
                run_rss(db, src)
            elif src.type == "html":
                run_html(db, src)
            else:
                raise ValueError(f"Unsupported source type: {src.type}")
            entry["ok"] = True
            stats["ok"] += 1
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            stats["errors"] += 1
        stats["per_source"].append(entry)
    return stats
