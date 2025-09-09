"""
test_registry.py — Verify scraper registry discovery.

Place at: tests/test_registry.py
Run from the repo root (folder that contains app/).

What this does:
  - Imports and calls app.registry.discover().
  - Asserts the result is a dict mapping names → callables.
  - Sanity check: all values in the registry are callable.

Why it matters:
  - Ensures scraper registry auto-discovery works and doesn’t break.
  - Prevents regressions where registry entries are non-callables.

Prereqs:
  - app/registry.py must define a discover() function returning a dict.

Common examples:
  pytest -q tests/test_registry.py
      # Run just this test

  pytest -k registry
      # Run by keyword across the test suite
"""

from app.registry import discover


def test_discover_scrapers_imports():
    reg = discover()
    assert isinstance(reg, dict)
    # Every entry must map to a callable
    assert all(callable(fn) for fn in reg.values())
