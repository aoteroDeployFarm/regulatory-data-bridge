from sqlalchemy.orm import Session
from app.db.crud import upsert_source

def seed(db: Session):
    candidates = [
        # Federal
        {"name": "EPA – News Releases (RSS)", "url": "https://www.epa.gov/newsreleases/search/rss", "jurisdiction": "US", "type": "rss"},
        {"name": "OSHA – News Releases (HTML)", "url": "https://www.osha.gov/news/newsreleases", "jurisdiction": "US", "type": "html"},

        # State
        {"name": "Texas RRC – News (HTML)", "url": "https://www.rrc.texas.gov/news/", "jurisdiction": "TX", "type": "html"},
        {"name": "Colorado ECMC – Media & Press", "url": "https://ecmc.state.co.us/media.html", "jurisdiction": "CO", "type": "html"},
        {"name": "Colorado ECMC – Library", "url": "https://ecmc.state.co.us/library.html", "jurisdiction": "CO", "type": "html"},

        # NFPA (JSON-LD likely present)
        {"name": "NFPA – News, Blogs, and Articles", "url": "https://www.nfpa.org/news-blogs-and-articles", "jurisdiction": "US", "type": "html"},
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
