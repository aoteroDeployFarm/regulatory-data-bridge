#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, json, argparse, urllib.parse, requests

DEFAULT_BASE = "http://127.0.0.1:8000"

def get_openapi(base_url: str) -> dict:
    r = requests.get(f"{base_url}/openapi.json", timeout=(10, 30))
    r.raise_for_status()
    return r.json()

def allowed_methods(openapi: dict, path: str) -> set[str]:
    paths = openapi.get("paths", {})
    entry = paths.get(path, {})
    return {m.upper() for m in entry.keys()}

def call_json(method: str, url: str, headers: dict, json_body: dict | None, timeout_read: int):
    # connection timeout 10s, read timeout configurable
    return requests.request(method, url, headers=headers, json=json_body, timeout=(10, timeout_read))

def call_ingest(base_url: str, state: str, limit: int, force: bool, api_key: str | None, timeout_read: int):
    spec = get_openapi(base_url)
    hdrs = {}
    if api_key:
        hdrs["X-API-Key"] = api_key
    payload = {"state": state, "limit": limit, "force": force}

    methods_ingest = allowed_methods(spec, "/admin/ingest")
    methods_scrape_all = allowed_methods(spec, "/admin/scrape-all")

    if methods_ingest:
        if "POST" in methods_ingest:
            r = call_json("POST", f"{base_url}/admin/ingest", hdrs, payload, timeout_read)
            r.raise_for_status()
            return r.json()
        if "GET" in methods_ingest:
            qs = urllib.parse.urlencode(payload)
            r = call_json("GET", f"{base_url}/admin/ingest?{qs}", hdrs, None, timeout_read)
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"/admin/ingest exists but not GET/POST: {methods_ingest}")

    if methods_scrape_all:
        if "POST" in methods_scrape_all:
            r = call_json("POST", f"{base_url}/admin/scrape-all", hdrs, payload, timeout_read)
            r.raise_for_status()
            return r.json()
        if "GET" in methods_scrape_all:
            qs = urllib.parse.urlencode(payload)
            r = call_json("GET", f"{base_url}/admin/scrape-all?{qs}", hdrs, None, timeout_read)
            r.raise_for_status()
            return r.json()

    raise RuntimeError("Neither /admin/ingest nor /admin/scrape-all are available")

def main():
    ap = argparse.ArgumentParser(description="Admin client for local ingest (auto-detects method).")
    ap.add_argument("ingest", nargs="?", help="(fixed) use as: admin_client.py ingest", default="ingest")
    ap.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    ap.add_argument("--state", required=True, help="State code, e.g. co")
    ap.add_argument("--limit", type=int, default=25, help="Max sources to process")
    ap.add_argument("--force", action="store_true", help="Force refresh")
    ap.add_argument("--timeout", type=int, default=300, help="Read timeout seconds (default 300)")
    ap.add_argument("--api-key", default=None, help="Optional X-API-Key value")
    args = ap.parse_args()

    try:
        out = call_ingest(
            base_url=args.base,
            state=args.state.lower(),
            limit=args.limit,
            force=bool(args.force),
            api_key=args.api_key,
            timeout_read=args.timeout,
        )
        print(json.dumps(out, indent=2))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
