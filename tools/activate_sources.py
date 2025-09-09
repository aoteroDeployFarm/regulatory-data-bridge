#!/usr/bin/env python3
"""
activate_sources.py — Bulk-activate (or deactivate) sources in your DB.

Place at: tools/activate_sources.py
Run from the repo root (folder that contains app/).

What this does:
  - Connects to your app's database using whichever session construct is available
    (get_session, SessionLocal, or get_db), with a last-resort engine from settings.
  - Toggles Source.active for rows you specify (all, by state filter, and/or only
    those already inactive/active).
  - Optional seeding step (runs app/seeds/seed_sources.py) before toggling.
  - Supports a dry-run mode that reports counts without committing.

Prereqs:
  - A Source ORM model at app.db.models.Source or app.db.models.source.Source
  - A DB session exposed at app.db.session (get_session | SessionLocal | get_db)
  - SQLAlchemy installed and configured via settings (DATABASE_URL or SQLALCHEMY_DATABASE_URI)

Common examples:
  python tools/activate_sources.py
      # Activate ALL sources

  python tools/activate_sources.py --seed
      # Seed first (idempotent), then activate all

  python tools/activate_sources.py --only-inactive
      # Activate only those currently inactive

  python tools/activate_sources.py --deactivate
      # Deactivate ALL sources

  python tools/activate_sources.py --deactivate --only-inactive
      # Deactivate only those currently active

  python tools/activate_sources.py --states CO,TX,CA
      # Scope by jurisdictions (case-insensitive)

  python tools/activate_sources.py --dry-run
      # Show how many rows would change, but do not commit

Notes:
  - --states accepts a comma-separated list (e.g., "co, tx ,CA"); whitespace is fine.
  - --only-inactive pairs with either activate (default) or --deactivate to limit flips.
  - Exit code 0 on success; non-zero on error.
"""
from __future__ import annotations

import argparse
import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

# Ensure repo root (parent of tools/) is importable
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --- Resolve DB session context in a backward-compatible way ---
@contextmanager
def _ctx_from_get_session(mod, engine):
    """Wrap a get_session(...) contextmanager if available."""
    get_session = getattr(mod, "get_session", None)
    if get_session is None or not callable(get_session):
        raise RuntimeError("get_session not callable")
    try:
        # Try get_session(engine) first, then get_session()
        try:
            cm = get_session(engine) if engine is not None else get_session()
        except TypeError:
            cm = get_session()
        with cm as db:
            yield db
    except Exception:
        raise


@contextmanager
def _ctx_from_sessionlocal(mod, engine):
    """Wrap a SessionLocal factory if available."""
    SessionLocal = getattr(mod, "SessionLocal", None)
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
def _ctx_from_get_db(mod):
    """Drive a FastAPI-style get_db generator to run its finally: close()."""
    get_db = getattr(mod, "get_db", None)
    if get_db is None or not callable(get_db):
        raise RuntimeError("get_db not callable")
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        # Advance generator to execute its finally: block
        try:
            next(gen)
        except StopIteration:
            pass


def _resolve_engine_and_ctx():
    """
    Return (engine, session_ctx) where session_ctx is a contextmanager yielding a DB session.
    Tries, in order:
      1) app.db.session.get_session(...),
      2) app.db.session.SessionLocal,
      3) app.db.session.get_db(),
      4) Create engine from settings if needed.
    """
    # Import session module
    try:
        sess_mod = importlib.import_module("app.db.session")
    except Exception as e:
        raise SystemExit(
            "ERROR: Could not import app.db.session. Ensure you're running from the repo root "
            "and the project has app/db/session.py\nDetails: %r" % (e,)
        )

    engine = getattr(sess_mod, "engine", None)

    # If get_session is provided, prefer it
    get_session = getattr(sess_mod, "get_session", None)
    if callable(get_session):
        try:
            @_wrap_name("get_session")
            @contextmanager
            def session_ctx():
                with _ctx_from_get_session(sess_mod, engine) as db:
                    yield db
            return engine, session_ctx
        except Exception:
            pass

    # Next try SessionLocal
    if getattr(sess_mod, "SessionLocal", None) is not None:
        @_wrap_name("SessionLocal")
        @contextmanager
        def session_ctx():
            with _ctx_from_sessionlocal(sess_mod, engine) as db:
                yield db
        return engine, session_ctx

    # Next try get_db generator
    if callable(getattr(sess_mod, "get_db", None)):
        @_wrap_name("get_db")
        @contextmanager
        def session_ctx():
            with _ctx_from_get_db(sess_mod) as db:
                yield db
        return engine, session_ctx

    # As a last resort, try to build our own engine from settings
    try:
        settings_mod = importlib.import_module("app.core.settings")
        settings = getattr(settings_mod, "settings", settings_mod)
        db_url = (
            getattr(settings, "DATABASE_URL", None)
            or getattr(settings, "SQLALCHEMY_DATABASE_URI", None)
            or os.getenv("DATABASE_URL")
        )
        if not db_url:
            raise RuntimeError("No DATABASE_URL found in settings or env.")
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(db_url, future=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

        @contextmanager
        def session_ctx():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        return engine, session_ctx
    except Exception as e:
        raise SystemExit(
            "ERROR: Could not resolve a database session. "
            "Please expose one of: get_session, SessionLocal, or get_db in app/db/session.py\n"
            f"Details: {e}"
        )


def _wrap_name(name):
    # Decorator no-op used only for labeling; keeps code tidy
    def deco(fn):  # noqa: D401
        return fn
    return deco


def _import_source_model():
    """Try the common locations for the Source model."""
    # 1) app.db.models:Source
    try:
        mdl = importlib.import_module("app.db.models")
        if hasattr(mdl, "Source"):
            return getattr(mdl, "Source")
    except Exception:
        pass
    # 2) app.db.models.source:Source
    try:
        mdl = importlib.import_module("app.db.models.source")
        return getattr(mdl, "Source")
    except Exception as e:
        raise SystemExit(
            "ERROR: Could not import Source model from app.db.models or app.db.models.source\n"
            f"Details: {e}"
        )


def maybe_seed(verbose: bool = True) -> None:
    """Run app/seeds/seed_sources.py if present (idempotent)."""
    seed_path = REPO_ROOT / "app" / "seeds" / "seed_sources.py"
    if not seed_path.exists():
        if verbose:
            print("Seed script not found; skipping seeding.")
        return
    if verbose:
        print(f"Seeding via {seed_path} ...")
    import runpy
    runpy.run_path(str(seed_path), run_name="__main__")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bulk activate/deactivate sources.")
    p.add_argument(
        "--deactivate",
        action="store_true",
        help="Set active=False for matched sources (default: activate=True).",
    )
    p.add_argument(
        "--only-inactive",
        action="store_true",
        help="Only flip rows currently inactive (or active if --deactivate).",
    )
    p.add_argument(
        "--states",
        type=str,
        default="",
        help="Comma-separated jurisdiction codes (e.g., CO,TX,CA).",
    )
    p.add_argument(
        "--seed",
        action="store_true",
        help="Run seeding before toggling.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Show counts; do not commit.",
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if args.seed:
        maybe_seed(verbose=args.verbose)

    # Resolve DB session + engine
    engine, session_ctx = _resolve_engine_and_ctx()
    Source = _import_source_model()

    # Toggle flags
    target_value = not args.deactivate  # True => activate, False => deactivate

    with session_ctx() as db:
        q = db.query(Source)

        # Optional state filter
        if args.states:
            wanted = {s.strip().upper() for s in args.states.split(",") if s.strip()}
            if wanted:
                q = q.filter(Source.jurisdiction.in_(wanted))

        total = q.count()

        if args.only_inactive and target_value is True:
            q = q.filter(Source.active == False)  # noqa: E712
        elif args.only_inactive and target_value is False:
            q = q.filter(Source.active == True)  # noqa: E712

        if args.dry_run:
            to_change = q.count()
            action = "activate" if target_value else "deactivate"
            scope = f"states={args.states}" if args.states else "all states"
            print(f"[DRY RUN] Would {action} {to_change} / {total} sources ({scope}).")
            return 0

        changed = q.update({Source.active: target_value})
        db.commit()

    action = "Activated" if target_value else "Deactivated"
    scope = f" in [{args.states}]" if args.states else ""
    print(f"{action} {changed} / {total} sources{scope}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
