# tests/test_registry.py
from app.registry import discover

def test_discover_scrapers_imports():
    reg = discover()
    assert isinstance(reg, dict)
    # Every entry must map to a callable
    assert all(callable(fn) for fn in reg.values())
