# tests/test_scrapers/test_ferc_scraper.py
from scrapers.federal.ferc_gov.check_updates import check_for_update
import scrapers.federal.ferc_gov.check_updates as mod

def test_check_for_update_smoke(monkeypatch):
    def fake_fetch():
        return "<html><h2>News</h2><a>Item A</a></html>"
    monkeypatch.setattr(mod, "fetch_html", fake_fetch)
    res = check_for_update()
    assert "updated" in res and "url" in res
