#!/usr/bin/env python3
"""
run_all_scrapers.py — Discover and run generated scrapers concurrently; write JSONL results.

Place at: tools/run_all_scrapers.py
Run from the repo root (folder that contains app/).

What this does:
  - Recursively finds scraper modules under scrapers/state/**/*_scraper.py.
  - Imports each module and calls check_for_update().
  - Runs scrapers in a thread pool and streams results to a timestamped JSONL file.
  - Prints a concise console summary (ok/updated/failed) and per-scraper status.

Output format (one JSON object per line):
  {
    "source_id": "<file_stem>",
    "state": "<state_code or _unknown>",
    "module": "scrapers.state.<code>.<name>_scraper",
    "path": "scrapers/state/<code>/<name>_scraper.py",
    "run_at": "YYYYMMDDTHHMMSSZ",
    "ok": true|false,
    "error": "<message if any>",
    "result": { ... original dict returned by check_for_update() ... }
  }

Common examples:
  # Run everything with 8 workers; show all results
  python tools/run_all_scrapers.py

  # Run only Texas and California scrapers, show only updated ones
  python tools/run_all_scrapers.py --state tx --state ca --only_updated

  # Limit to 20 scrapers matching 'health' in filename, increase workers
  python tools/run_all_scrapers.py --pattern health --limit 20 --workers 16

  # Use a different root folder and output directory
  python tools/run_all_scrapers.py --root scrapers/state --out data/runs

Notes:
  - A scraper is expected to define a callable check_for_update() → dict.
  - Failures are captured and recorded; the run continues.
  - Output file path is printed at the end (default: data/runs/scrape_<timestamp>.jsonl).
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCRAPERS_ROOT = Path("scrapers/state")


@dataclass(frozen=True)
class ScraperRef:
    state: str            # e.g. "tx"
    path: Path            # full path to file
    module_path: str      # e.g. "scrapers.state.tx.some_scraper"


def iter_scrapers(root: Path = SCRAPERS_ROOT) -> Iterable[ScraperRef]:
    for p in root.rglob("*_scraper.py"):
        # Expect structure: scrapers/state/<code>/<file>.py
        try:
            rel = p.relative_to(Path.cwd())
        except ValueError:
            rel = p
        parts = rel.with_suffix("").parts
        # Build module path from parts
        module_path = ".".join(parts)
        # State code is the directory after "state"
        try:
            i = parts.index("state")
            state = parts[i + 1]
        except Exception:
            state = "_unknown"
        yield ScraperRef(state=state, path=p, module_path=module_path)


def load_module(mp: str):
    return importlib.import_module(mp)


def run_one(ref: ScraperRef) -> Tuple[ScraperRef, Dict[str, Any] | None, str | None]:
    try:
        mod = load_module(ref.module_path)
        fn = getattr(mod, "check_for_update", None)
        if not callable(fn):
            return ref, None, f"No check_for_update() in {ref.module_path}"
        res_any: Any = fn()
        if not isinstance(res_any, dict):
            return ref, None, f"Unexpected result type from {ref.module_path}: {type(res_any).__name__}"
        return ref, res_any, None
    except Exception as e:
        tb = traceback.format_exc(limit=3)
        return ref, None, f"{e.__class__.__name__}: {e}\n{tb}"


def main():
    ap = argparse.ArgumentParser(description="Run generated scrapers and persist results.")
    ap.add_argument("--root", default=str(SCRAPERS_ROOT), help="Root folder for scrapers (default: scrapers/state)")
    ap.add_argument("--state", action="append", help="Filter by state code (e.g., --state tx --state ca)")
    ap.add_argument("--pattern", help="Substring filter on filename (case-insensitive)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of scrapers (for quick tests)")
    ap.add_argument("--workers", type=int, default=8, help="Threaded concurrency")
    ap.add_argument("--only_updated", action="store_true", help="Print only updated results")
    ap.add_argument("--out", default="data/runs", help="Directory to write JSONL output")
    args = ap.parse_args()

    root = Path(args.root)
    refs = list(iter_scrapers(root))

    # filters
    if args.state:
        wanted = {s.lower() for s in args.state}
        refs = [r for r in refs if r.state.lower() in wanted]
    if args.pattern:
        pat = args.pattern.lower()
        refs = [r for r in refs if pat in r.path.name.lower()]
    if args.limit and args.limit > 0:
        refs = refs[: args.limit]

    if not refs:
        print("No scrapers matched.")
        return

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outfile = outdir / f"scrape_{ts}.jsonl"

    ok = 0
    upd = 0
    fail = 0

    print(f"Running {len(refs)} scraper(s) with {args.workers} workers…")
    with ThreadPoolExecutor(max_workers=args.workers) as ex, outfile.open("w", encoding="utf-8") as fh:
        futures = [ex.submit(run_one, r) for r in refs]
        for fut in as_completed(futures):
            ref, res, err = fut.result()
            record = {
                "source_id": ref.path.stem,
                "state": ref.state,
                "module": ref.module_path,
                "path": str(ref.path),
                "run_at": ts,
                "ok": err is None,
            }
            if err is not None:
                record["error"] = err
                fail += 1
                print(f"✗ {ref.state} {ref.path.name}: {err.splitlines()[0]}")
            else:
                ok += 1
                # normalize + write
                if isinstance(res, dict):
                    record["result"] = res
                    if res.get("updated"):
                        upd += 1
                        if args.only_updated:
                            print(f"✓ UPDATED {ref.state} {ref.path.name}")
                    else:
                        if not args.only_updated:
                            print(f"• {ref.state} {ref.path.name} (no change)")
                else:
                    record["result"] = None
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\nDone: ok={ok} updated={upd} failed={fail}")
    print(f"Output → {outfile}")


if __name__ == "__main__":
    main()
