"""
test_openapi_contract.py — Contract test to ensure OpenAPI spec is served.

Place at: tests/test_openapi_contract.py
Run from the repo root (folder that contains app/).

What this does:
  - Requests GET /openapi.json from the running service at http://127.0.0.1:8000.
  - Asserts a 200 OK and parses the JSON.
  - Verifies that expected endpoints are present in the spec (sanity check).

Prereqs:
  - The API server must be running locally on port 8000.
  - requests library must be installed (pip install requests).

Common examples:
  # Run this specific test
  pytest -q tests/test_openapi_contract.py

  # Run all tests but stop at first failure
  pytest -x
"""

import requests


def test_openapi_served():
    r = requests.get("http://127.0.0.1:8000/openapi.json", timeout=5)
    assert r.status_code == 200
    data = r.json()
    # sanity: our paths exist
    for p in ["/health", "/scrapers", "/check-site-update", "/batch-check", "/metrics"]:
        assert p in data["paths"]
