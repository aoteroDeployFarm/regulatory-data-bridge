from __future__ import annotations
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import Source
from app.scrapers.rss import run_rss
from app.scrapers.html import run_html

def run_ingest_once(db: Session, only_active: bool = True) -> dict:
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
