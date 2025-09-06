from sqlalchemy.orm import Session
from sqlalchemy import select
from ..db.models import Source
from ..scrapers.rss import run_rss
from ..scrapers.html import run_html

def run_ingest_once(db: Session, only_active: bool = True):
    q = select(Source)
    if only_active:
        q = q.where(Source.active == True)
    sources = db.execute(q).scalars().all()
    for src in sources:
        if src.type == "rss":
            run_rss(db, src)
        elif src.type == "html":
            run_html(db, src)
