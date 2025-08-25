import requests

def test_openapi_served():
    r = requests.get("http://127.0.0.1:8000/openapi.json", timeout=5)
    assert r.status_code == 200
    data = r.json()
    # sanity: our paths exist
    for p in ["/health", "/scrapers", "/check-site-update", "/batch-check", "/metrics"]:
        assert p in data["paths"]
