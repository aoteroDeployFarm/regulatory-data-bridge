#!/usr/bin/env python3
"""
Simple client for your FastAPI admin endpoints.

Commands:
  - list:   List discovered scrapers (optionally filter by state)
  - scrape: Run one scraper by source_id (with optional state/selector/force)
  - bulk:   Run many scrapers via the API (filter by state/pattern/limit)
            and optionally write results to JSONL

Examples:
  python scripts/admin_client.py list
  python scripts/admin_client.py list --state tx

  python scripts/admin_client.py scrape \
    --source-id alabama-gsa-state-al-us-ogb_html_scraper

  python scripts/admin_client.py scrape \
    --source-id air-quality-permits_html_scraper --state wa --force

  python scripts/admin_client.py bulk --state ca --pattern air --limit 5 --only-updated --out data/runs/api_bulk.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import httpx


def pretty(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def list_scrapers(base_url: str, state: str | None, timeout: float) -> List[Dict[str, Any]]:
    params = {}
    if state:
        params["state"] = state
    with httpx.Client(base_url=base_url, timeout=timeout) as c:
        r = c.get("/admin/scrapers", params=params)
        r.raise_for_status()
        return r.json()


def run_scraper(
    base_url: str,
    source_id: str,
    state: str | None,
    selector: str | None,
    force: bool,
    timeout: float,
) -> Dict[str, Any]:
    params = {"source_id": source_id}
    if state:
        params["state"] = state
    if selector:
        params["selector"] = selector
    if force:
        params["force"] = "true"
    with httpx.Client(base_url=base_url, timeout=timeout) as c:
        r = c.post("/admin/scrape", params=params)
        r.raise_for_status()
        return r.json()


def bulk_scrape(
    base_url: str,
    state: str | None,
    pattern: str | None,
    limit: int,
    only_updated: bool,
    force: bool,
    out_path: Path | None,
    timeout: float,
) -> None:
    items = list_scrapers(base_url, state, timeout)
    if pattern:
        pat = pattern.lower()
        items = [it for it in items if pat in it["source_id"].lower() or pat in it["path"].lower()]
    if limit and limit > 0:
        items = items[:limit]
    if not items:
        print("No scrapers matched.")
        return

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fh = out_path.open("w", encoding="utf-8")
    else:
        fh = None

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ok = upd = fail = 0

    for it in items:
        sid = it["source_id"]
        st = it["state"]
        try:
            res = run_scraper(base_url, sid, st, selector=None, force=force, timeout=timeout)
            ok += 1
            is_upd = bool(res.get("updated"))
            if is_upd:
                upd += 1
                print(f"✓ UPDATED {st} {sid}")
            else:
                if not only_updated:
                    print(f"• {st} {sid} (no change)")
            if fh:
                rec = {
                    "source_id": sid,
                    "state": st,
                    "module": it.get("module"),
                    "path": it.get("path"),
                    "run_at": ts,
                    "ok": True,
                    "result": res,
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except httpx.HTTPStatusError as e:
            fail += 1
            print(f"✗ {st} {sid}: HTTP {e.response.status_code} — {e.response.text[:200]}")
            if fh:
                rec = {
                    "source_id": sid,
                    "state": st,
                    "module": it.get("module"),
                    "path": it.get("path"),
                    "run_at": ts,
                    "ok": False,
                    "error": f"HTTP {e.response.status_code}: {e.response.text}",
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            fail += 1
            print(f"✗ {st} {sid}: {e}")
            if fh:
                rec = {
                    "source_id": sid,
                    "state": st,
                    "module": it.get("module"),
                    "path": it.get("path"),
                    "run_at": ts,
                    "ok": False,
                    "error": str(e),
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if fh:
        fh.close()
        print(f"\nWrote results → {out_path}")

    print(f"Done: ok={ok} updated={upd} failed={fail}")


def main():
    ap = argparse.ArgumentParser(description="Admin client for scraper API")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    ap.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout (seconds)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List scrapers")
    p_list.add_argument("--state", help="Two-letter state code (e.g., tx)")

    p_scrape = sub.add_parser("scrape", help="Run a single scraper by source_id")
    p_scrape.add_argument("--source-id", required=True, help="Filename stem without .py (see 'list')")
    p_scrape.add_argument("--state", help="Two-letter state code to disambiguate")
    p_scrape.add_argument("--selector", help="CSS selector override (HTML scrapers)")
    p_scrape.add_argument("--force", action="store_true", help="Clear cache before running")

    p_bulk = sub.add_parser("bulk", help="Run multiple scrapers via API")
    p_bulk.add_argument("--state", help="Filter by state code")
    p_bulk.add_argument("--pattern", help="Substring filter on source_id/path")
    p_bulk.add_argument("--limit", type=int, default=0, help="Limit number of scrapers")
    p_bulk.add_argument("--only-updated", action="store_true", help="Print only updated results")
    p_bulk.add_argument("--force", action="store_true", help="Clear cache before each run")
    p_bulk.add_argument("--out", type=Path, help="Write JSONL results to this file (e.g., data/runs/api_bulk.jsonl)")

    args = ap.parse_args()

    if args.cmd == "list":
        data = list_scrapers(args.base_url, args.state, args.timeout)
        print(pretty(data))
        return

    if args.cmd == "scrape":
        res = run_scraper(
            base_url=args.base_url,
            source_id=args.source_id,
            state=args.state,
            selector=args.selector,
            force=args.force,
            timeout=args.timeout,
        )
        print(pretty(res))
        return

    if args.cmd == "bulk":
        bulk_scrape(
            base_url=args.base_url,
            state=args.state,
            pattern=args.pattern,
            limit=args.limit,
            only_updated=args.only_updated,
            force=args.force,
            out_path=args.out,
            timeout=args.timeout,
        )
        return


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
