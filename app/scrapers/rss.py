from __future__ import annotations
from datetime import datetime
import feedparser
from sqlalchemy.orm import Session
from ..db.crud import create_or_update_doc
from ..db.models import Source

def parse_dt(entry):
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6])
    except Exception:
        pass
    return None

def run_rss(db: Session, src: Source):
    feed = feedparser.parse(src.url)
    for e in feed.entries:
        title = getattr(e, "title", "(untitled)")
        link = getattr(e, "link", None)
        if not link:
            continue
        published_at = parse_dt(e)
        snippet = getattr(e, "summary", None)
        metadata = {
            "rss_id": getattr(e, "id", None),
            "tags": getattr(e, "tags", None),
        }
        create_or_update_doc(
            db,
            source_id=src.id,
            title=title,
            url=link,
            published_at=published_at,
            text=snippet,
            metadata=metadata,          # pass as `metadata` param; CRUD stores in .meta
            jurisdiction=src.jurisdiction,
        )
