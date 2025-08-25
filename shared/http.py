# shared/http.py
from __future__ import annotations
import time
from typing import Optional
import httpx

_client: Optional[httpx.Client] = None

def get_client(timeout: float = 15.0) -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "regulatory-data-bridge/0.1"},
        )
    return _client

def fetch_text(url: str, *, retries: int = 2, backoff: float = 0.6) -> str:
    client = get_client()
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = client.get(url)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(backoff * (2 ** attempt))
    raise last_err  # type: ignore[misc]
