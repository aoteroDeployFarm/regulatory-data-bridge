from pathlib import Path
import pkgutil, importlib

def test_no_legacy_states_dir():
    assert not (Path("scrapers")/"states").exists(), "Legacy scrapers/states/ should not exist"

def test_all_scrapers_importable():
    # import every scrapers.*.check_updates module
    found = 0
    for mod in pkgutil.walk_packages(["scrapers"], prefix="scrapers."):
        if not mod.ispkg and mod.name.endswith(".check_updates"):
            importlib.import_module(mod.name)
            found += 1
    assert found > 0, "No scraper modules discovered"
