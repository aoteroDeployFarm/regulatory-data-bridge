from sqlalchemy.orm import Session
from app.db.crud import upsert_source

def seed(db: Session):
    candidates = [
        {"name": "OSHA News Releases", "url": "https://www.osha.gov/news/rss.xml", "jurisdiction": "US", "type": "rss"},
        {"name": "EPA Press Releases", "url": "https://www.epa.gov/newsreleases/search/rss", "jurisdiction": "US", "type": "rss"},
        {"name": "Texas RRC – News", "url": "https://rrc.texas.gov/news/rss", "jurisdiction": "TX", "type": "rss"},
        {"name": "Colorado Oil & Gas – News", "url": "https://cogcc.state.co.us/announcements.html", "jurisdiction": "CO", "type": "html"},
        {"name": "NFPA News & Research", "url": "https://www.nfpa.org/News-and-Research", "jurisdiction": "US", "type": "html"},
    ]
    for c in candidates:
        upsert_source(
            db,
            name=c["name"],
            url=c["url"],
            jurisdiction=c["jurisdiction"],
            type_=c["type"],
            active=True,
        )

if __name__ == "__main__":
    from app.db.session import SessionLocal
    db = SessionLocal()
    seed(db)
    db.close()
