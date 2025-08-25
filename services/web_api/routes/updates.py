from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _pick_scraper(url: str, registry: dict[str, callable] | None):
    if not registry:
        return None
    # Longest key substring match wins (specific > generic)
    candidates = [(k, fn) for k, fn in registry.items() if k in url]
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: len(x[0]), reverse=True)[0][1]


@router.get("/check-site-update")
def check_site_update(url: str, request: Request):
    """
    Example:
      GET /check-site-update?url=https://www.ferc.gov/news-events/news
    """
    registry = getattr(request.app.state, "scraper_map", {}) or {}
    fn = _pick_scraper(url, registry)
    if not fn:
        raise HTTPException(status_code=400, detail="No scraper registered for this URL")
    return fn()


@router.get("/batch-check")
def batch_check(request: Request):
    """
    Run all registered scrapers and return a consolidated report.
    """
    registry = getattr(request.app.state, "scraper_map", {}) or {}
    out = []
    for key, fn in registry.items():
        try:
            res = fn()
            res["scraper"] = key
            out.append(res)
        except Exception as e:
            out.append({"scraper": key, "error": str(e)})
    return {"count": len(out), "results": out}


@router.get("/scrapers")
def list_scrapers(request: Request):
    """
    Inspect the currently-registered scrapers (keys are TARGET_URL anchors).
    """
    registry = getattr(request.app.state, "scraper_map", {}) or {}
    return {"count": len(registry), "keys": sorted(registry.keys())}
