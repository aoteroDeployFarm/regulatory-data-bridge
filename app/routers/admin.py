# app/routers/admin.py
from __future__ import annotations

import importlib
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/admin", tags=["admin"])

SCRAPER_ROOT = Path("scrapers/state")  # scrapers/state/<state_code>/*.py
SCRAPER_SUFFIX = "_scraper.py"


@dataclass(frozen=True)
class ScraperInfo:
    state: str            # two-letter code (folder name)
    source_id: str        # filename stem without .py
    module: str           # import path like scrapers.state.tx.texas-..._html_scraper
    path: str             # filesystem path for reference


def _iter_scraper_files(root: Path = SCRAPER_ROOT) -> Iterable[Path]:
    if not root.exists():
        return []
    return root.rglob(f"*{SCRAPER_SUFFIX}")


def _state_code_from_path(p: Path) -> str:
    # scrapers/state/<state>/<file>.py
    try:
        return p.parent.name.lower()
    except Exception:
        return ""


def _module_from_path(p: Path) -> str:
    # Convert file path -> module path, e.g. scrapers/state/tx/foo.py -> scrapers.state.tx.foo
    return p.with_suffix("").as_posix().replace("/", ".")


def _discover_all() -> List[ScraperInfo]:
    out: List[ScraperInfo] = []
    for fp in _iter_scraper_files():
        state = _state_code_from_path(fp)
        src_id = fp.stem
        mod = _module_from_path(fp)
        out.append(ScraperInfo(state=state, source_id=src_id, module=mod, path=str(fp)))
    out.sort(key=lambda s: (s.state, s.source_id))
    return out


def _filter_scrapers(items: List[ScraperInfo], state: Optional[str], pattern: Optional[str]) -> List[ScraperInfo]:
    if state:
        s = state.lower()
        items = [it for it in items if it.state == s]
    if pattern:
        pat = pattern.lower()
        items = [it for it in items if pat in it.source_id.lower() or pat in it.path.lower()]
    return items


def _per_scraper_cache_dir(scraper_path: str) -> Path:
    """New scheme: scrapers/state/<code>/.cache/<scraper_stem>/"""
    p = Path(scraper_path)
    return p.parent / ".cache" / p.stem


def _legacy_state_cache_dir(scraper_path: str) -> Path:
    """Old scheme: scrapers/state/<code>/.cache/ (shared). We keep this to optionally clean up."""
    p = Path(scraper_path)
    return p.parent / ".cache"


def _prepare_cache_for(scraper_path: str, force: bool) -> Path:
    """
    Ensure the per-scraper .cache folder exists next to the scraper module file.
    If force=True, delete that folder first, then recreate.
    """
    cache_dir = _per_scraper_cache_dir(scraper_path)
    if force and cache_dir.exists():
        shutil.rmtree(cache_dir, ignore_errors=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _clear_cache_for(scraper_path: str, include_legacy: bool = False) -> Dict[str, Any]:
    """
    Remove the per-scraper cache directory. Optionally also remove legacy state-level .cache
    (NOT recommended unless you know nothing else is using it).
    """
    per = _per_scraper_cache_dir(scraper_path)
    out = {"per_scraper": str(per), "per_removed": False, "legacy_removed": False}
    if per.exists():
        shutil.rmtree(per, ignore_errors=True)
        out["per_removed"] = True
    if include_legacy:
        legacy = _legacy_state_cache_dir(scraper_path)
        if legacy.exists():
            # Only remove if it's empty after removing this scraper's folder
            try:
                # If other subdirs exist, we leave it.
                leftover = [x for x in legacy.iterdir()]
                if not leftover:
                    shutil.rmtree(legacy, ignore_errors=True)
                    out["legacy_removed"] = True
            except Exception:
                pass
    return out


def _run_module(info: ScraperInfo) -> Dict[str, Any]:
    """
    Import a scraper module and run check_for_update().
    All generated scrapers expose check_for_update() -> dict
    """
    mod = importlib.import_module(info.module)
    if not hasattr(mod, "check_for_update"):
        raise RuntimeError(f"{info.module} has no check_for_update()")
    res = mod.check_for_update()  # type: ignore[attr-defined]
    if isinstance(res, dict):
        meta = res.get("meta") or {}
        meta.update({
            "runner_state": info.state,
            "runner_source_id": info.source_id,
            "runner_module": info.module,
        })
        res["meta"] = meta
    return res


@router.get("/scrapers")
def list_scrapers(
    state: str | None = Query(default=None, description="Filter by 2-letter state code, e.g. 'tx'"),
    pattern: str | None = Query(default=None, description="Substring filter on source_id or path (case-insensitive)"),
) -> List[Dict[str, Any]]:
    items = _filter_scrapers(_discover_all(), state, pattern)
    return [
        {"state": it.state, "source_id": it.source_id, "module": it.module, "path": it.path}
        for it in items
    ]


@router.api_route("/scrape", methods=["POST"])
@router.api_route("/scrape/", methods=["POST"])
def run_scraper(
    source_id: str = Query(..., description="Filename stem without .py (see /admin/scrapers)"),
    state: str | None = Query(default=None, description="2-letter state code to disambiguate if duplicate stems"),
    force: bool = Query(default=False, description="Clear the scraper's per-scraper .cache before running"),
) -> Dict[str, Any]:
    candidates = _filter_scrapers(_discover_all(), state, None)
    matches = [it for it in candidates if it.source_id == source_id]

    if not matches:
        hints = [it.source_id for it in _filter_scrapers(_discover_all(), state, source_id)]
        raise HTTPException(
            status_code=404,
            detail={"error": f"source_id '{source_id}' not found", "did_you_mean": hints[:10]},
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Ambiguous source_id '{source_id}'", "candidates": [m.path for m in matches]},
        )

    info = matches[0]
    _prepare_cache_for(info.path, force)

    try:
        res = _run_module(info)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.api_route("/scrape-all", methods=["GET", "POST"])
@router.api_route("/scrape-all/", methods=["GET", "POST"])
def run_many_scrapers(
    state: str | None = Query(default=None, description="2-letter state code filter (e.g., 'tx')"),
    pattern: str | None = Query(default=None, description="Substring filter on source_id or path (e.g., 'fire' or 'nfpa')"),
    limit: int = Query(default=0, ge=0, description="Max number to run (0 means no limit)"),
    force: bool = Query(default=False, description="Clear per-scraper .cache before running"),
    only_updated: bool = Query(default=False, description="Return only results where updated==True"),
) -> Dict[str, Any]:
    items = _filter_scrapers(_discover_all(), state, pattern)
    attempted = len(items)
    if limit and limit > 0:
        items = items[:limit]

    if not items:
        return {
            "ok": True,
            "attempted": attempted,
            "count": 0,
            "updated": 0,
            "failed": 0,
            "state": state,
            "pattern": pattern,
            "results": [],
            "limit": limit,
            "only_updated": only_updated,
            "force": force,
            "run_at": datetime.now(timezone.utc).isoformat(),
        }

    ok = 0
    upd = 0
    fail = 0
    results: List[Dict[str, Any]] = []

    for info in items:
        try:
            _prepare_cache_for(info.path, force)
            res = _run_module(info)
            updated = bool(res.get("updated")) if isinstance(res, dict) else False
            ok += 1
            if updated:
                upd += 1
            if only_updated and not updated:
                continue
            results.append({
                "state": info.state,
                "source_id": info.source_id,
                "module": info.module,
                "path": info.path,
                "ok": True,
                "updated": updated,
                "result": res,
            })
        except Exception as e:
            fail += 1
            results.append({
                "state": info.state,
                "source_id": info.source_id,
                "module": info.module,
                "path": info.path,
                "ok": False,
                "error": str(e),
            })

    return {
        "ok": True,
        "attempted": attempted,
        "count": ok,
        "updated": upd,
        "failed": fail,
        "state": state,
        "pattern": pattern,
        "limit": limit,
        "only_updated": only_updated,
        "force": force,
        "results": results,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }


@router.api_route("/cache/clear", methods=["POST", "GET"])
def clear_caches(
    state: str | None = Query(default=None, description="Filter by 2-letter state code"),
    pattern: str | None = Query(default=None, description="Substring filter on source_id or path"),
    limit: int = Query(default=0, ge=0, description="Max number to clear (0 means no limit)"),
    include_legacy: bool = Query(default=False, description="Also remove old shared state-level .cache if empty"),
) -> Dict[str, Any]:
    """
    Clear per-scraper caches without running scrapers.
    Example:
      /admin/cache/clear?state=tx&pattern=fire
    """
    items = _filter_scrapers(_discover_all(), state, pattern)
    attempted = len(items)
    if limit and limit > 0:
        items = items[:limit]

    cleared: List[Dict[str, Any]] = []
    for info in items:
        out = _clear_cache_for(info.path, include_legacy=include_legacy)
        cleared.append({
            "state": info.state,
            "source_id": info.source_id,
            "per_scraper_dir": out["per_scraper"],
            "per_removed": out["per_removed"],
            "legacy_removed": out["legacy_removed"],
        })

    return {
        "ok": True,
        "attempted": attempted,
        "cleared": len(cleared),
        "state": state,
        "pattern": pattern,
        "include_legacy": include_legacy,
        "results": cleared,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
