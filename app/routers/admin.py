# app/routers/admin.py
from __future__ import annotations

import importlib
import inspect
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/admin", tags=["admin"])

# Where generated scrapers live (by our generator)
SCRAPERS_ROOT = Path("scrapers") / "state"


# ---------------------------
# Discovery helpers
# ---------------------------

@dataclass(frozen=True)
class ScraperRef:
    state: str            # e.g. "tx"
    path: Path            # full path to file
    module_path: str      # e.g. "scrapers.state.tx.some_scraper"
    source_id: str        # filename stem (without .py)

def _iter_scrapers(root: Path = SCRAPERS_ROOT) -> Iterable[ScraperRef]:
    if not root.exists():
        return []
    for p in root.rglob("*_scraper.py"):
        # Expect: scrapers/state/<code>/<file>.py
        parts = p.with_suffix("").parts
        try:
            i = parts.index("state")
            state = parts[i + 1]
        except Exception:
            state = "_unknown"
        module_path = ".".join(parts)  # safe on any OS
        source_id = p.stem
        yield ScraperRef(state=state, path=p, module_path=module_path, source_id=source_id)

def _find_scrapers_by_source_id(source_id: str) -> List[ScraperRef]:
    src_lower = source_id.lower().removesuffix(".py")
    return [r for r in _iter_scrapers() if r.source_id.lower() == src_lower]


# ---------------------------
# Response models
# ---------------------------

class ScraperInfo(BaseModel):
    source_id: str
    state: str
    module: str
    path: str

class ScrapeResponse(BaseModel):
    source_id: str
    state: str
    module: str
    path: str
    ok: bool
    updated: bool | None = None
    result: Dict | None = None
    error: str | None = None


# ---------------------------
# Routes
# ---------------------------

@router.get("/scrapers", response_model=List[ScraperInfo])
def list_scrapers(state: Optional[str] = Query(None, description="Filter by two-letter state code (e.g., 'tx')")):
    items = []
    for ref in _iter_scrapers():
        if state and ref.state.lower() != state.lower():
            continue
        items.append(ScraperInfo(source_id=ref.source_id, state=ref.state, module=ref.module_path, path=str(ref.path)))
    return items


@router.post("/scrape", response_model=ScrapeResponse)
def run_scraper(
    source_id: str = Query(..., description="Filename stem without .py, e.g. 'alabama-…_html_scraper'"),
    state: Optional[str] = Query(None, description="Two-letter state code to disambiguate if multiple exist"),
    selector: Optional[str] = Query(None, description="Optional CSS selector override (HTML scrapers only)"),
    force: bool = Query(False, description="If true, clears the scraper's .cache before running"),
):
    matches = _find_scrapers_by_source_id(source_id)
    if state:
        matches = [m for m in matches if m.state.lower() == state.lower()]

    if not matches:
        raise HTTPException(404, f"Scraper '{source_id}' not found" + (f" in state '{state}'" if state else ""))

    if len(matches) > 1:
        # Ask caller to specify state to disambiguate
        opts = ", ".join(sorted({m.state for m in matches}))
        raise HTTPException(400, f"Multiple scrapers named '{source_id}' exist. Specify ?state= one of: {opts}")

    ref = matches[0]

    # Optional: clear cache for a fresh run
    if force:
        cache_dir = ref.path.parent / ".cache"
        try:
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
        except Exception as e:
            # not fatal; we still attempt to run
            pass

    try:
        mod = importlib.import_module(ref.module_path)
    except Exception as e:
        raise HTTPException(500, f"Failed to import module '{ref.module_path}': {e}")

    fn = getattr(mod, "check_for_update", None)
    if not callable(fn):
        raise HTTPException(500, f"check_for_update() not found in '{ref.module_path}'")

    # Call with selector if the function supports it (HTML scrapers)
    try:
        kwargs: Dict = {}
        if selector:
            try:
                sig = inspect.signature(fn)
                if "selector" in sig.parameters:
                    kwargs["selector"] = selector
            except Exception:
                # If we cannot inspect, just try without kwargs
                kwargs = {}
        res = fn(**kwargs) if kwargs else fn()  # type: ignore[misc]
    except Exception as e:
        raise HTTPException(500, f"Error while running scraper: {e}")

    if not isinstance(res, dict):
        raise HTTPException(500, f"Unexpected result type from scraper: {type(res).__name__}")

    return ScrapeResponse(
        source_id=ref.source_id,
        state=ref.state,
        module=ref.module_path,
        path=str(ref.path),
        ok=True,
        updated=bool(res.get("updated")),
        result=res,
        error=None,
    )
