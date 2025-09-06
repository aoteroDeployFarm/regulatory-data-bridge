def test_search_documents(client):
    # assuming test client + fixtures are set up
    r = client.get("/documents", params={"q": "NFPA"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)
