from __future__ import annotations
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from ..db.crud import create_or_update_doc
from ..db.models import Source
from urllib.parse import urljoin

def run_html(db: Session, src: Source):
    resp = requests.get(src.url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select("a"):
        href = a.get("href")
        title = a.get_text(strip=True)
        if not href or not title:
            continue
        if href.startswith("/"):
            href = urljoin(src.url, href)

        # naive date extraction
        text_block = a.find_parent().get_text(" ", strip=True) if a.find_parent() else title
        m = re.search(r"(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4})", text_block)
        published_at = None
        if m:
            try:
                published_at = datetime.strptime(m.group(1), "%B %d, %Y")
            except Exception:
                pass

        create_or_update_doc(
            db,
            source_id=src.id,
            title=title,
            url=href,
            published_at=published_at,
            text=None,
            metadata=None,              # keep signature consistent
            jurisdiction=src.jurisdiction,
        )
