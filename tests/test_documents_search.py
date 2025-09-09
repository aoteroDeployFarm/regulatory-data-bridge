"""
test_document_search.py — Smoke test for the /documents search endpoint.

Place at: tests/test_document_search.py
Run from the repo root (folder that contains app/).

What this does:
  - Issues a GET /documents?q=NFPA using the test client fixture.
  - Asserts a 200 OK and that the response body is a JSON list.

Prereqs:
  - A pytest test client fixture named `client` (e.g., in tests/conftest.py).
  - Your API exposes GET /documents with a `q` query parameter.

Common examples:
  # Run just this test with minimal output
  pytest -q tests/test_documents_search.py

  # Run by keyword across the suite
  pytest -k test_documents_search -q
"""

def test_search_documents(client):
    # assuming test client + fixtures are set up
    r = client.get("/documents", params={"q": "NFPA"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
