#!/usr/bin/env python3
"""
Cleanup utility for Regulatory-Data-Bridge admin endpoints.

Examples
--------
# Run all default cleanups against local server
python tools/cleanup.py --base http://127.0.0.1:8000 --run all

# Run only specific steps
python tools/cleanup.py --base http://127.0.0.1:8000 --run fragment-only trailing-hash non-http titles

# Add some URL-substring purges (uses /cleanup/by-url-pattern)
python tools/cleanup.py --base http://127.0.0.1:8000 --by-url-pattern mailto: tel: "/contact" "/about"

# Dry-run (just shows what would be called)
python tools/cleanup.py --base http://127.0.0.1:8000 --run all --dry-run

"""

from __future__ import annotations
import argparse
import sys
import time
from typing import Dict, Any, List, Tuple

import requests

DEFAULT_STEPS = [
    "fragment-only",   # POST /admin/cleanup/fragment-only
    "trailing-hash",   # POST /admin/cleanup/trailing-hash
    "non-http",        # POST /admin/cleanup/non-http
    "titles",          # POST /admin/cleanup/titles-exact (runs multiple titles)
]

DEFAULT_TITLES = [
    "Home",
    "Skip To Main Content",
]

# You can add common junk URL substrings here if you want to sweep them regularly.
# These use /admin/cleanup/by-url-pattern (SQL LIKE '%pattern%').
COMMON_URL_PATTERNS = [
    "mailto:",
    "tel:",
    "/contact",
    "/about",
    "/forms",
    "/resources",
    "/site-policies",
    "?p=",
    "#",   # often caught by fragment/trailing, but this also removes mid-URL hashes
]

def post(base: str, path: str, params: Dict[str, Any] | None = None, timeout: int = 30) -> Tuple[bool, Dict[str, Any]]:
    url = base.rstrip("/") + path
    try:
        r = requests.post(url, params=params, timeout=timeout)
        ok = (200 <= r.status_code < 300)
        data = {}
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return ok, {"status": r.status_code, "url": url, "params": params or {}, "response": data}
    except Exception as e:
        return False, {"status": 0, "url": url, "params": params or {}, "error": repr(e)}

def run_fragment_only(base: str, dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    return run_with_retries(lambda: post(base, "/admin/cleanup/fragment-only"), "fragment-only", dry, retries, delay)

def run_trailing_hash(base: str, dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    return run_with_retries(lambda: post(base, "/admin/cleanup/trailing-hash"), "trailing-hash", dry, retries, delay)

def run_non_http(base: str, dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    return run_with_retries(lambda: post(base, "/admin/cleanup/non-http"), "non-http", dry, retries, delay)

def run_titles(base: str, titles: List[str], dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    results = {"step": "titles", "calls": []}
    for t in titles:
        label = f"titles-exact:{t}"
        fn = lambda: post(base, "/admin/cleanup/titles-exact", params={"title": t})
        res = run_with_retries(fn, label, dry, retries, delay)
        results["calls"].append(res)
    return results

def run_by_url_patterns(base: str, patterns: List[str], dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    results = {"step": "by-url-pattern", "calls": []}
    for p in patterns:
        label = f"by-url:{p}"
        fn = lambda: post(base, "/admin/cleanup/by-url-pattern", params={"pattern": p})
        res = run_with_retries(fn, label, dry, retries, delay)
        results["calls"].append(res)
    return results

def run_with_retries(call, label: str, dry: bool, retries: int, delay: float) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"label": label, "ok": False, "attempts": 0}
    if dry:
        entry.update({"dry_run": True})
        return entry
    last = None
    for i in range(1, retries + 1):
        ok, details = call()
        entry["attempts"] = i
        last = details
        if ok:
            entry["ok"] = True
            entry["response"] = details
            break
        time.sleep(delay)
    if not entry["ok"]:
        entry["error"] = last
    return entry

def print_summary(results: List[Dict[str, Any]]) -> None:
    total_deleted = 0
    print("\n=== Cleanup Summary ===")
    for res in results:
        step = res.get("step") or res.get("label")
        if "calls" in res:
            print(f"\nStep: {step}")
            for call in res["calls"]:
                _print_call(call)
                # Try to extract deleted count if present
                deleted = (call.get("response", {}).get("response", {}) or {}).get("deleted")
                if isinstance(deleted, int):
                    total_deleted += deleted
        else:
            _print_call(res)
            deleted = (res.get("response", {}).get("response", {}) or {}).get("deleted")
            if isinstance(deleted, int):
                total_deleted += deleted
    print(f"\nTotal deleted: {total_deleted}")

def _print_call(call: Dict[str, Any]) -> None:
    label = call.get("label", "call")
    if call.get("dry_run"):
        print(f"  - {label}: DRY-RUN (no request sent)")
        return
    ok = call.get("ok")
    attempts = call.get("attempts", 0)
    if ok:
        resp = call.get("response", {})
        status = resp.get("status")
        url = resp.get("url")
        body = resp.get("response", {})
        print(f"  - {label}: OK (status {status}, attempts {attempts}) -> {url}")
        if isinstance(body, dict):
            deleted = body.get("deleted")
            extra = {k: v for k, v in body.items() if k not in ("ok", "deleted")}
            if deleted is not None:
                print(f"      deleted={deleted}")
            if extra:
                print(f"      extra={extra}")
    else:
        err = call.get("error", {})
        print(f"  - {label}: FAILED after {attempts} attempts -> {err}")

def parse_args(argv: List[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Admin cleanup helper for Regulatory-Data-Bridge")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="Base URL of the running API")
    ap.add_argument("--run", nargs="+", default=["all"],
                    choices=["all", "fragment-only", "trailing-hash", "non-http", "titles", "by-url"],
                    help="Which cleanup steps to run")
    ap.add_argument("--title", action="append", default=None,
                    help="Extra exact titles to remove (can be provided multiple times)")
    ap.add_argument("--by-url-pattern", dest="patterns", action="append", default=None,
                    help="Additional URL substring patterns to purge with /cleanup/by-url-pattern (can be repeated)")
    ap.add_argument("--retries", type=int, default=2, help="Retries per step")
    ap.add_argument("--delay", type=float, default=0.3, help="Seconds between retries")
    ap.add_argument("--dry-run", action="store_true", help="Print what would be called without deleting")
    return ap.parse_args(argv)

def main(argv: List[str]) -> int:
    args = parse_args(argv)
    steps = args.run
    if "all" in steps:
        steps = DEFAULT_STEPS + ["by-url"]  # include URL pattern sweeps too

    titles = (args.title or []) + DEFAULT_TITLES
    patterns = (args.patterns or []) + COMMON_URL_PATTERNS

    results: List[Dict[str, Any]] = []

    if "fragment-only" in steps:
        results.append(run_fragment_only(args.base, args.dry_run, args.retries, args.delay))
    if "trailing-hash" in steps:
        results.append(run_trailing_hash(args.base, args.dry_run, args.retries, args.delay))
    if "non-http" in steps:
        results.append(run_non_http(args.base, args.dry_run, args.retries, args.delay))
    if "titles" in steps:
        results.append(run_titles(args.base, titles, args.dry_run, args.retries, args.delay))
    if "by-url" in steps and patterns:
        results.append(run_by_url_patterns(args.base, patterns, args.dry_run, args.retries, args.delay))

    print_summary(results)
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
