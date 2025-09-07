# app/scrapers/rss.py
from __future__ import annotations
from datetime import datetime
from typing import Optional
import feedparser
from sqlalchemy.orm import Session
from app.db.crud import create_or_update_doc
from app.db.models import Source
from app.scrapers.http import make_session
from app.scrapers.html import run_html  # <- fallback

def parse_dt(entry) -> Optional[datetime]:
    try:
        if getattr(entry, "published_parsed", None):
            return datetime(*entry.published_parsed[:6])
    except Exception:
        pass
    return None

def _looks_like_html(content_type: str | None, body: bytes) -> bool:
    if content_type and ("html" in content_type.lower()):
        return True
    head = body[:512].lower()
    return b"<html" in head or b"<!doctype html" in head

def run_rss(db: Session, src: Source):
    s = make_session()
    r = s.get(src.url, timeout=25, allow_redirects=True)
    r.raise_for_status()

    if _looks_like_html(r.headers.get("Content-Type"), r.content):
        # Not actually XML; many sites serve an HTML error page to bots → fallback to HTML scraping
        run_html(db, src)
        return

    feed = feedparser.parse(r.content)
    if feed.bozo and getattr(feed, "bozo_exception", None):
        # If RSS parsing fails, fallback to HTML scraping once
        run_html(db, src)
        return

    for e in feed.entries or []:
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
            metadata=metadata,
            jurisdiction=src.jurisdiction,
        )
