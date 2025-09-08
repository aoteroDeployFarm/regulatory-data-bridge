#!/usr/bin/env python3
"""
tools/ingest_all.py — trigger ingestion via the running API.

Examples:
  python3 tools/ingest_all.py                 # cached ingest
  python3 tools/ingest_all.py --force         # force fresh
  python3 tools/ingest_all.py --state CO,TX   # if your build supports state filter
"""
from __future__ import annotations
import argparse, json, sys, urllib.parse, urllib.request

def call(url: str, method: str = "GET"):
    req = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(req, timeout=600) as r:
        data = r.read()
    try:
        return json.loads(data.decode("utf-8"))
    except Exception:
        return data.decode("utf-8")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--force", action="store_true")
    p.add_argument("--state", default="", help="Comma-separated (if supported by your API)")
    args = p.parse_args()

    # Prefer POST /admin/ingest; optionally pass force=true
    params = {}
    if args.force: params["force"] = "true"
    if args.state: params["state"] = args.state

    if params:
        q = "?" + urllib.parse.urlencode(params)
    else:
        q = ""

    url = f"{args.base_url}/admin/ingest{q}"
    print("POST", url)
    out = call(url, method="POST")
    print(out if isinstance(out, str) else json.dumps(out, indent=2))

if __name__ == "__main__":
    sys.exit(main())
