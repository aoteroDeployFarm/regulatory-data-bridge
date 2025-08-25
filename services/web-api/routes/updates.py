from fastapi import APIRouter
from scrapers.ferc.gov import check_updates

router = APIRouter()

@router.get("/check-site-update")
def check_site_update(url: str):
    if "ferc.gov/news-events/news" in url:
        return check_updates.check_for_update()
    return {"error": "No scraper available for this URL"}
# services/web-api/routes/updates.py
from fastapi import APIRouter, HTTPException
from typing import Callable, Dict

# Import scrapers you’ve completed
from scrapers.federal.ferc.gov import check_updates as ferc
from scrapers.federal.boem.gov import check_updates as boem
from scrapers.federal.bsee.gov import check_updates as bsee
from scrapers.conservation.ca.gov import check_updates as calgem

router = APIRouter()

SCRAPER_MAP: Dict[str, Callable[[], dict]] = {
    "ferc.gov/news-events/news": ferc.check_for_update,
    "boem.gov/newsroom": boem.check_for_update,
    "www.bsee.gov/newsroom/latest-news": bsee.check_for_update,
    "www.conservation.ca.gov/calgem": calgem.check_for_update,
}

def pick_scraper(url: str) -> Callable[[], dict] | None:
    for key, fn in SCRAPER_MAP.items():
        if key in url:
            return fn
    return None

@router.get("/check-site-update")
def check_site_update(url: str):
    fn = pick_scraper(url)
    if not fn:
        raise HTTPException(status_code=400, detail="No scraper registered for this URL")
    return fn()
