#!/usr/bin/env python3
# app/scrapers/http.py
"""
HTTP session factory for scrapers.

Provides:
- A preconfigured `requests.Session` with:
  * Default headers (user-agent, accept, etc.)
  * Retry logic for transient errors (429, 500, 502, 503, 504)
  * Certifi CA bundle for SSL verification

Usage:
------
    from app.scrapers.http import make_session

    session = make_session()
    r = session.get("https://example.com")
    r.raise_for_status()
    print(r.text)

Notes:
------
- Retries: 3 attempts, exponential backoff (0.5s, 1s, 2s)
- Allowed retry methods: GET, HEAD
- Uses Chrome-like UA string with project identifier
"""

from __future__ import annotations
from typing import Optional

import certifi
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36 RegulatoryDataBridge/0.1"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/rss+xml;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def make_session(headers: Optional[dict] = None) -> requests.Session:
    """Return a preconfigured requests.Session for scraper use."""
    s = requests.Session()
    h = DEFAULT_HEADERS.copy()
    if headers:
        h.update(headers)
    s.headers.update(h)

    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)

    # Use certifi CA bundle
    s.verify = certifi.where()
    return s
