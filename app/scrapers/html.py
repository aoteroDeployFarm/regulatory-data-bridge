# app/scrapers/html.py
from __future__ import annotations
import re, json, html
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from app.db.crud import create_or_update_doc
from app.db.models import Source
from app.scrapers.http import make_session

DATE_PAT = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b")

def _clean_title(s: str) -> str:
    s = html.unescape((s or "").strip())
    # Normalize a few common curly quotes/dashes that show up in CSVs
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2014", "-").replace("\u2013", "-")
    return s

def _same_host(href: str, base: str) -> bool:
    try:
        a, b = urlparse(href), urlparse(base)
        return (a.netloc == "" or a.netloc == b.netloc)
    except Exception:
        return True

def _try_parse_date_text(text: str) -> datetime | None:
    m = DATE_PAT.search(text or "")
    if m:
        try:
            return datetime.strptime(m.group(0), "%B %d, %Y")
        except Exception:
            return None
    return None

def _ingest_doc(db: Session, src: Source, title: str, href: str, published_at: datetime | None):
    create_or_update_doc(
        db,
        source_id=src.id,
        title=_clean_title(title)[:1024] or "(untitled)",
        url=href,
        published_at=published_at,
        text=None,
        metadata=None,
        jurisdiction=src.jurisdiction,
    )

# ---------- Site-specific: Texas RRC ----------
_RRC_BAD_PATH_PREFIXES = (
    "/about-us", "/apps", "/forms", "/resource-center", "/general-counsel",
    "/surface-mining", "/gas-services", "/pipeline-safety", "/critical-infrastructure",
    "/contact-us", "/hearings", "/legal", "/public-engagement", "/oil-and-gas",
    "/site-policies", "/newsletters", "/announcements",
)

def _parse_rrc_news(db: Session, src: Source, soup: BeautifulSoup):
    base = src.url
    seen = set()

    # Keep only /news/... links. RRC article URLs look like /news/MMDDYY-... or /news/YYYYMMDD-...
    anchors = soup.select("a[href]")
    for a in anchors:
        href = (a.get("href") or "").strip()
        title = (a.get_text(" ", strip=True) or "").strip()
        if not href or not title:
            continue

        if href.startswith("/"):
            href = urljoin(base, href)
        if not _same_host(href, base):
            continue

        p = urlparse(href).path or ""
        if not p.startswith("/news/"):
            # exclude obvious nav/utility
            if p.startswith(_RRC_BAD_PATH_PREFIXES) or p in ("/", ""):
                continue
            # also drop anchors and hash-only links
            if href.endswith("#") or href.startswith("#"):
                continue
            continue

        if href in seen:
            continue
        seen.add(href)

        # Try date from URL: /news/MMDDYY-... or /news/YYYYMMDD-...
        pub = None
        m6 = re.search(r"/news/(\d{6})-", p)   # e.g., 090525 => 2025-09-05 (MMDDYY)
        m8 = re.search(r"/news/(\d{8})-", p)   # e.g., 20250113 => 2025-01-13 (YYYYMMDD)
        if m8:
            y, m, d = m8.group(1)[0:4], m8.group(1)[4:6], m8.group(1)[6:8]
            try: pub = datetime(int(y), int(m), int(d))
            except Exception: pass
        elif m6:
            mm, dd, yy = m6.group(1)[0:2], m6.group(1)[2:4], m6.group(1)[4:6]
            # Assume 20YY (good enough for current content)
            try: pub = datetime(2000 + int(yy), int(mm), int(dd))
            except Exception: pass

        if pub is None:
            # fallback: nearby text
            block = a.find_parent()
            pub = _try_parse_date_text(block.get_text(" ", strip=True) if block else title)

        _ingest_doc(db, src, title, href, pub)

# ---------- Generic parser with JSON-LD fallback ----------
def _generic_html(db: Session, src: Source, soup: BeautifulSoup):
    base = src.url
    seen = set()
    found_any = False

    # 1) JSON-LD NewsArticle / BlogPosting
    for tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue

        def iter_items(obj):
            if isinstance(obj, dict):
                yield obj
                for v in obj.values():
                    yield from iter_items(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from iter_items(v)

        for item in iter_items(data):
            if not isinstance(item, dict):
                continue
            tp = item.get("@type")
            if tp in ("NewsArticle", "BlogPosting", "Article"):
                title = item.get("headline") or item.get("name")
                href = item.get("url") or item.get("mainEntityOfPage") or ""
                if not title or not href:
                    continue
                if href.startswith("/"):
                    href = urljoin(base, href)
                if not _same_host(href, base):
                    continue
                if href in seen:
                    continue
                seen.add(href)

                pub = None
                for key in ("datePublished", "dateCreated", "dateModified"):
                    if item.get(key):
                        try:
                            val = str(item[key]).split("T")[0]
                            pub = datetime.fromisoformat(val)
                            break
                        except Exception:
                            pass

                _ingest_doc(db, src, title, href, pub)
                found_any = True

    # 2) Anchor fallback
    if not found_any:
        anchors = soup.select("a[href]")
        for a in anchors:
            href = (a.get("href") or "").strip()
            title = (a.get_text(" ", strip=True) or "").strip()
            if not href or not title:
                continue
            if href.startswith("/"):
                href = urljoin(base, href)
            if not _same_host(href, base):
                continue
            if href in seen:
                continue
            seen.add(href)

            block = a.find_parent()
            pub = _try_parse_date_text(block.get_text(" ", strip=True) if block else title)
            _ingest_doc(db, src, title, href, pub)

def run_html(db: Session, src: Source):
    s = make_session()
    r = s.get(src.url, timeout=20, allow_redirects=True)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    host = urlparse(src.url).netloc.lower()
    if host.endswith("rrc.texas.gov"):
        _parse_rrc_news(db, src, soup)
    else:
        _generic_html(db, src, soup)
