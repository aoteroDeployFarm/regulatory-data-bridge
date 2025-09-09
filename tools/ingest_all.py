#!/usr/bin/env python3
"""
ingest_all.py — Trigger ingestion of sources via the running API.

Place at: tools/ingest_all.py
Run from the repo root (folder that contains app/).

What this does:
  - Calls your running FastAPI service’s /admin/ingest endpoint.
  - Sends a POST request (preferred) with optional query parameters.
  - Prints the API’s JSON (pretty-printed) or raw string response.

Prereqs:
  - Your API must be running and expose /admin/ingest (POST).
  - Default URL is http://127.0.0.1:8000 (override with --base-url).

Common examples:
  python tools/ingest_all.py
      # Ingest all sources, cached mode (default)

  python tools/ingest_all.py --force
      # Force fresh ingest

  python tools/ingest_all.py --state CO,TX
      # Ingest sources filtered by jurisdiction(s), if supported by API

  python tools/ingest_all.py --base-url http://localhost:9000 --force
      # Point to custom API base

Exit codes:
  - 0 => Successful request (response printed)
  - non-zero => Error occurred (e.g., API unreachable, invalid response)

Notes:
  - Timeout for each request is fixed at 600 seconds.
  - Falls back to printing raw response text if JSON decoding fails.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request


def call(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return data.decode("utf-8")


def main():
    p = argparse.ArgumentParser(description="Trigger ingestion via /admin/ingest endpoint.")
    p.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    p.add_argument("--force", action="store_true", help="Force fresh ingest")
    p.add_argument(
        "--state", default="", help="Comma-separated jurisdiction codes, if supported by API"
    )
    args = p.parse_args()

    # Prefer POST /admin/ingest; optionally pass force=true
    params = {}
    if args.force:
        params["force"] = "true"
    if args.state:
        params["state"] = args.state

    q = "?" + urllib.parse.urlencode(params) if params else ""
    url = f"{args.base_url}/admin/ingest{q}"

    print("POST", url)
    out = call(url, method="POST")
    print(out if isinstance(out, str) else json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
