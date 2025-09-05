# app/registry.py
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Dict, Iterable

SCRAPERS_DIR = Path(__file__).resolve().parent.parent / "scrapers"

def _iter_scraper_paths(root: Path = SCRAPERS_DIR) -> Iterable[Path]:
    if not root.exists():
        return []
    for p in root.rglob("*_scraper.py"):
        # ignore caches/tests
        if any(part in {".cache", "__pycache__", "tests"} for part in p.parts):
            continue
        yield p

def _load_module_from_path(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if not spec or not spec.loader:  # pragma: no cover
        raise ImportError(f"Failed to load spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)     # type: ignore[attr-defined]
    return mod

def discover(root: Path | None = None) -> Dict[str, ModuleType]:
    """Discover generated scraper modules under scrapers/ and return {source_id: module}."""
    root = root or SCRAPERS_DIR
    found: Dict[str, ModuleType] = {}
    for path in _iter_scraper_paths(root):
        mod = _load_module_from_path(path)
        src_id = path.stem  # filename without .py
        found[src_id] = mod
    return found
