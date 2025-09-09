#!/usr/bin/env python3
"""
upsert_state_sites.py — Bulk upsert & activate state regulatory source URLs.

Place at: tools/upsert_state_sites.py
Run from the repo root (folder that contains app/).

What this does:
  - Reads a JSON file of state → [URLs] (default: ./state-website-data/state-website-data.json).
  - Upserts by URL (idempotent). Existing rows keep their current name to avoid churn.
  - Ensures UNIQUE(name): tracks names in DB + this run; only appends a short hash if needed.
  - De-dupes URLs within each state while preserving their order.
  - Sets jurisdiction/state, type = ("pdf" if URL ends in .pdf else "html"), and active=True.
  - Optional: commit after each state (for resilience) or run in dry-run mode (no writes).

Input JSON format:
  {
    "Alabama": ["https://example.gov/a", "https://example.gov/b"],
    "AK":       ["https://alaska.gov/x"],
    ...
  }
  Keys may be full state names or USPS codes; values are lists of URL strings.

Prereqs:
  - Source model available in:
      app.db.models.Source  or  app.db.models.source.Source (or SourceModel)
  - A DB session exposed via one of:
      app.db.session.get_session(...), app.db.session.SessionLocal, or app.db.session.get_db()

Common examples:
  python tools/upsert_state_sites.py
      # Upsert all states from default JSON; commit once at the end

  python tools/upsert_state_sites.py --dry-run
      # Show inserts/updates per state; do not write/commit

  python tools/upsert_state_sites.py --states CA,TX,CO
      # Limit operation to the listed states (names or USPS codes)

  python tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json --commit-per-state
      # Use a custom file and commit after each state for incremental safety

Notes:
  - Name generation uses "JUR – host/path" and appends a short hash iff duplicate.
  - The script accepts full names or USPS codes in both the JSON and --states filter.
  - Exit code 0 on success; non-zero on fatal error (e.g., session/model resolution).
"""
from __future__ import annotations

import sys
import json
import argparse
import importlib
import hashlib
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

# --- Make repo root importable (parent of tools/) ---
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# --- State name -> USPS code ---
USPS = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "District of Columbia": "DC",
}

# ---------- JSON loader ----------
def load_sites(json_path: Path) -> dict[str, list[str]]:
    """
    Expecting: { "Alabama": ["https://...", ...], "AK": ["https://...", ...], ... }
    Keys may be full names or USPS codes. Values are lists of URL strings.
    """
    if not json_path.exists():
        raise SystemExit(f"ERROR: sites file not found: {json_path}")
    try:
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise SystemExit(f"ERROR: could not read JSON {json_path}: {e}")
    if not isinstance(data, dict):
        raise SystemExit("ERROR: JSON must be an object mapping state -> [urls].")

    cleaned: dict[str, list[str]] = {}
    for key, urls in data.items():
        if not isinstance(key, str) or not isinstance(urls, list):
            continue
        # de-dupe while preserving order
        seen = set()
        norm_urls: list[str] = []
        for u in urls:
            if isinstance(u, str):
                s = u.strip()
                if s and s not in seen:
                    seen.add(s)
                    norm_urls.append(s)
        if norm_urls:
            cleaned[key.strip()] = norm_urls
    if not cleaned:
        raise SystemExit("ERROR: no valid state -> urls found in JSON.")
    return cleaned

# ---------- DB session helpers (supports multiple layouts) ----------
@contextmanager
def _ctx_from_get_session(sess_mod, engine):
    get_session = getattr(sess_mod, "get_session", None)
    if not callable(get_session):
        raise RuntimeError("get_session not callable")
    try:
        try:
            cm = get_session(engine) if engine is not None else get_session()
        except TypeError:
            cm = get_session()
        with cm as db:
            yield db
    except Exception:
        raise

@contextmanager
def _ctx_from_sessionlocal(sess_mod, engine):
    SessionLocal = getattr(sess_mod, "SessionLocal", None)
    if SessionLocal is None:
        raise RuntimeError("SessionLocal not found")
    db = SessionLocal()
    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            pass

@contextmanager
def _ctx_from_get_db(sess_mod):
    get_db = getattr(sess_mod, "get_db", None)
    if not callable(get_db):
        raise RuntimeError("get_db not callable")
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

def get_session_ctx():
    try:
        sess_mod = importlib.import_module("app.db.session")
    except Exception as e:
        raise SystemExit(f"ERROR: import app.db.session failed: {e}")
    engine = getattr(sess_mod, "engine", None)
    if callable(getattr(sess_mod, "get_session", None)):
        return lambda: _ctx_from_get_session(sess_mod, engine)
    if getattr(sess_mod, "SessionLocal", None) is not None:
        return lambda: _ctx_from_sessionlocal(sess_mod, engine)
    if callable(getattr(sess_mod, "get_db", None)):
        return lambda: _ctx_from_get_db(sess_mod)
    raise SystemExit("Could not resolve DB session (need get_session, SessionLocal, or get_db).")

def get_source_model():
    for mod_name in ("app.db.models", "app.db.models.source"):
        try:
            mdl = importlib.import_module(mod_name)
        except Exception:
            continue
        for attr in ("Source", "SourceModel"):
            if hasattr(mdl, attr):
                return getattr(mdl, attr)
    raise SystemExit("ERROR: Source model not found in app.db.models")

# ---------- tiny utils ----------
def set_str(obj, candidates, value):
    for name in candidates:
        if hasattr(obj, name):
            setattr(obj, name, value)
            return True
    return False

def set_bool(obj, candidates, value: bool):
    for name in candidates:
        if hasattr(obj, name):
            setattr(obj, name, bool(value))
            return True
    return False

def infer_type(url: str) -> str:
    return "pdf" if url.lower().endswith(".pdf") else "html"

def short_hash(url: str, n: int = 8) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:n]

def base_name(jur: str, url: str, maxlen: int = 80) -> str:
    p = urlparse(url)
    host = p.netloc
    path = (p.path or "/").rstrip("/")
    txt = f"{jur} – {host}{path}"
    return txt if len(txt) <= maxlen else txt[: maxlen - 1] + "…"

def unique_name_for_insert(jur: str, url: str, used_names: set[str]) -> str:
    base = base_name(jur, url)
    if base not in used_names:
        used_names.add(base)
        return base
    suffix = short_hash(url)
    candidate = f"{base} · {suffix}"
    i = 2
    while candidate in used_names:
        candidate = f"{base} · {suffix}-{i}"
        i += 1
    used_names.add(candidate)
    return candidate

def upsert(db, Source, state_key: str, url: str, used_names: set[str], *, dry_run: bool = False):
    jur = USPS.get(state_key, state_key)  # accept full name or USPS code
    existing = db.query(Source).filter(getattr(Source, "url") == url).first()
    if existing:
        # keep existing name; just ensure metadata/flags
        set_str(existing, ["jurisdiction", "state"], jur)
        set_str(existing, ["type", "source_type"], infer_type(url))
        set_bool(existing, ["active", "is_active", "enabled"], True)
        return "update"
    # new row
    obj = Source()
    set_str(obj, ["name", "title"], unique_name_for_insert(jur, url, used_names))
    set_str(obj, ["url"], url)
    set_str(obj, ["jurisdiction", "state"], jur)
    set_str(obj, ["type", "source_type"], infer_type(url))
    set_bool(obj, ["active", "is_active", "enabled"], True)
    if not dry_run:
        db.add(obj)
    return "insert"

# ---------- CLI ----------
def parse_args():
    ap = argparse.ArgumentParser(description="Bulk upsert & activate state regulatory sources from JSON.")
    ap.add_argument(
        "--file",
        default=str(REPO_ROOT / "state-website-data" / "state-website-data.json"),
        help="Path to JSON file (default: ./state-website-data/state-website-data.json)",
    )
    ap.add_argument(
        "--states",
        default="",
        help="Comma-separated states to limit (accepts names or USPS codes, e.g., CA,Texas,CO)",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change; no commit",
    )
    ap.add_argument(
        "--commit-per-state",
        action="store_true",
        help="Commit after each state (more resilient to single-state errors)",
    )
    return ap.parse_args()

def main():
    args = parse_args()
    sites_json = Path(args.file).resolve()
    data = load_sites(sites_json)

    # normalize state filters (accept full names or USPS codes)
    allowed = None
    if args.states.strip():
        allowed = {s.strip().upper() for s in args.states.split(",") if s.strip()}

    Source = get_source_model()
    ctx_factory = get_session_ctx()

    totals = {"insert": 0, "update": 0}
    with ctx_factory() as db:
        # seed used_names from DB so we never duplicate an existing name
        NameCol = getattr(Source, "name")
        used_names = set(n for (n,) in db.query(NameCol).all())

        for state_key, urls in data.items():
            # filter states if requested
            if allowed:
                key_upper = state_key.upper()
                key_code = USPS.get(state_key, state_key).upper()
                if key_upper not in allowed and key_code not in allowed:
                    continue

            ins = upd = 0
            for u in urls:
                result = upsert(db, Source, state_key, u, used_names, dry_run=args.dry_run)
                if result == "insert":
                    ins += 1
                elif result == "update":
                    upd += 1

            jur = USPS.get(state_key, state_key)
            if args.dry_run:
                print(f"[DRY] {jur}: would insert={ins} update={upd}")
            else:
                totals["insert"] += ins
                totals["update"] += upd
                print(f"{jur}: inserted={ins} updated={upd}")
                if args.commit_per_state:
                    db.commit()

        if args.dry_run:
            print("[DRY] No changes committed.")
        else:
            if not args.commit_per_state:
                db.commit()
            print(f"Done. inserted={totals['insert']} updated={totals['update']}")

if __name__ == "__main__":
    raise SystemExit(main())
