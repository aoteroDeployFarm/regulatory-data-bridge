# services/web_api/registry.py
import sys, pkgutil, importlib
from pathlib import Path
from typing import Callable, Dict

def discover() -> Dict[str, Callable[[], dict]]:
    root = Path(__file__).resolve().parents[2]
    scrapers_dir = root / "scrapers"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    registry: Dict[str, Callable[[], dict]] = {}
    for mod in pkgutil.walk_packages([str(scrapers_dir)], prefix="scrapers."):
        if not mod.ispkg and mod.name.endswith(".check_updates"):
            m = importlib.import_module(mod.name)
            target = getattr(m, "TARGET_URL", None)
            fn = getattr(m, "check_for_update", None)
            if target and callable(fn):
                registry[target] = fn
    return registry
