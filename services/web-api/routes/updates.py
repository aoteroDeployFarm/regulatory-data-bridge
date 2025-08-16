from fastapi import APIRouter
from scrapers.ferc.gov import check_updates

router = APIRouter()

@router.get("/check-site-update")
def check_site_update(url: str):
    if "ferc.gov/news-events/news" in url:
        return check_updates.check_for_update()
    return {"error": "No scraper available for this URL"}
