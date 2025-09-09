"""
test_package_integrity.py — Sanity checks for scraper package integrity.

Place at: tests/test_package_integrity.py
Run from the repo root (folder that contains app/).

What this does:
  - Ensures the legacy directory scrapers/states/ is absent (should be removed).
  - Imports all modules matching scrapers.*.check_updates to verify they load.

Why it matters:
  - Prevents old/deprecated directories from lingering and breaking imports.
  - Confirms that scraper modules are syntactically valid and importable.

Prereqs:
  - Your scrapers/ package must be in the repo root (or added to PYTHONPATH).
  - Each scraper subpackage should contain a check_updates.py module.

Common examples:
  pytest -q tests/test_package_integrity.py
      # Run just these integrity tests

  pytest -k integrity
      # Run any test matching "integrity" in name
"""

from pathlib import Path
import pkgutil
import importlib


def test_no_legacy_states_dir():
    assert not (Path("scrapers") / "states").exists(), "Legacy scrapers/states/ should not exist"


def test_all_scrapers_importable():
    # import every scrapers.*.check_updates module
    found = 0
    for mod in pkgutil.walk_packages(["scrapers"], prefix="scrapers."):
        if not mod.ispkg and mod.name.endswith(".check_updates"):
            importlib.import_module(mod.name)
            found += 1
    assert found > 0, "No scraper modules discovered"
