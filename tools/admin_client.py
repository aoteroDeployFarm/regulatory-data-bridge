# tools/admin_client.py
import sys
import json
import argparse
import urllib.parse
import requests

DEFAULT_BASE = "http://127.0.0.1:8000"

def get_openapi(base_url: str) -> dict:
    r = requests.get(f"{base_url}/openapi.json", timeout=10)
    r.raise_for_status()
    return r.json()

def allowed_methods(openapi: dict, path: str) -> set[str]:
    paths = openapi.get("paths", {})
    entry = paths.get(path, {})
    return {m.upper() for m in entry.keys()}  # e.g. {"GET","POST"}

def call_ingest(base_url: str, state: str, limit: int, force: bool):
    # Inspect OpenAPI to choose path + method
    spec = get_openapi(base_url)
    methods_ingest = allowed_methods(spec, "/admin/ingest")
    methods_scrape_all = allowed_methods(spec, "/admin/scrape-all")

    payload = {"state": state, "limit": limit, "force": force}

    if methods_ingest:
        if "POST" in methods_ingest:
            r = requests.post(f"{base_url}/admin/ingest", json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        elif "GET" in methods_ingest:
            qs = urllib.parse.urlencode(payload)
            r = requests.get(f"{base_url}/admin/ingest?{qs}", timeout=60)
            r.raise_for_status()
            return r.json()
        else:
            raise RuntimeError(f"/admin/ingest exists but does not support GET/POST: {methods_ingest}")

    # Fallback for older route name
    if methods_scrape_all:
        if "POST" in methods_scrape_all:
            r = requests.post(f"{base_url}/admin/scrape-all", json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        elif "GET" in methods_scrape_all:
            qs = urllib.parse.urlencode(payload)
            r = requests.get(f"{base_url}/admin/scrape-all?{qs}", timeout=60)
            r.raise_for_status()
            return r.json()

    raise RuntimeError("Neither /admin/ingest nor /admin/scrape-all are available")

def main():
    ap = argparse.ArgumentParser(description="Admin client for local ingest")
    ap.add_argument("cmd", choices=["ingest"], help="Command")
    ap.add_argument("--base", default=DEFAULT_BASE, help="API base URL")
    ap.add_argument("--state", required=True, help="State code, e.g. co")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    try:
        if args.cmd == "ingest":
            out = call_ingest(args.base, args.state.lower(), args.limit, bool(args.force))
            print(json.dumps(out, indent=2))
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
