#!/usr/bin/env python3
"""
backfill_version.py — Seed initial DocumentVersion rows and fill missing hash/timestamps.

Place at: tools/backfill_version.py
Run from the repo root (folder that contains app/).

What this does:
  - Finds Document rows where current_hash is NULL/empty.
  - Derives a basis string (doc.text, or title + URL), computes a SHA-1,
    and fills: current_hash, first_seen_at, last_seen_at, last_changed_at.
  - If NO existing DocumentVersion for the doc, creates version_no=1 with a
    snapshot of the basis (first 20,000 chars) and change_type="ADDED".
  - Skips creating a duplicate version when one already exists, but still
    backfills missing fields on the Document row.

Prereqs:
  - Models available as either:
      app.db.model.Document / app.db.model.DocumentVersion
      OR app.db.models.Document / app.db.models.DocumentVersion
  - DATABASE_URL (e.g., postgres://..., sqlite:///dev.db) or DB_PATH env
    (defaults to "dev.db") unless you pass --db.

Common examples:
  # Use default DB (DATABASE_URL or sqlite:///dev.db), batching 500 rows
  python tools/backfill_version.py

  # Use a different batch size
  python tools/backfill_version.py --batch-size 2000

  # Point to a local sqlite file path (no scheme needed)
  python tools/backfill_version.py --db ./data/my.db

  # Point to a full SQLAlchemy URL explicitly
  python tools/backfill_version.py --db postgresql+psycopg://user:pass@localhost/dbname

Notes:
  - Safe to re-run: it won’t create duplicate versions when one exists.
  - Large tables: increase --batch-size for speed, decrease for lower memory.
  - Prints a summary: examined=<count> seeded_versions=<count>.
"""
from __future__ import annotations

import os
import hashlib
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# ---- Models (support singular/plural module naming) ----
try:
    from app.db.model import Document, DocumentVersion  # your repo uses this
except Exception:  # pragma: no cover
    from app.db.models import Document, DocumentVersion  # fallback


# ---- DB connection helpers ----
def _sqlite_url_from_path(path: str) -> str:
    if "://" in path:
        return path
    if os.path.isabs(path):
        return f"sqlite:///{path}"
    return f"sqlite:///{os.path.abspath(path)}"


DATABASE_URL = os.getenv("DATABASE_URL")  # e.g. postgres://... or sqlite:///dev.db
DB_PATH = os.getenv("DB_PATH", "dev.db")
ENGINE_URL = DATABASE_URL or _sqlite_url_from_path(DB_PATH)

engine = create_engine(ENGINE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---- Hashing ----
def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


# ---- Backfill logic ----
def choose_basis_text(doc: Document) -> str:
    text = (doc.text or "").strip()
    if text:
        return text
    return f"{(doc.title or '').strip()}\n{(doc.url or '').strip()}"


def backfill(batch_size: int = 500) -> None:
    total_seeded = 0
    total_seen = 0
    with session_scope() as db:
        q = (
            db.query(Document)
            .filter((Document.current_hash.is_(None)) | (Document.current_hash == ""))
            .order_by(Document.id.asc())
        )
        offset = 0
        while True:
            batch = q.offset(offset).limit(batch_size).all()
            if not batch:
                break
            for doc in batch:
                total_seen += 1
                basis = choose_basis_text(doc)
                h = sha1(basis)
                now = datetime.utcnow()

                # If a version exists, don't duplicate — just fill fields
                has_version = (
                    db.query(func.count(DocumentVersion.id))
                    .filter(DocumentVersion.doc_id == doc.id)
                    .scalar()
                )
                if has_version:
                    doc.current_hash = doc.current_hash or h
                    doc.first_seen_at = doc.first_seen_at or now
                    doc.last_seen_at = doc.last_seen_at or now
                    doc.last_changed_at = doc.last_changed_at or now
                    continue

                # Create initial version (version_no = 1)
                doc.current_hash = h
                doc.first_seen_at = now
                doc.last_seen_at = now
                doc.last_changed_at = now

                v = DocumentVersion(
                    doc_id=doc.id,
                    version_no=1,
                    content_hash=h,
                    title=doc.title,
                    snapshot=basis[:20000],
                    change_type="ADDED",
                )
                db.add(v)
                total_seeded += 1

            db.commit()
            offset += batch_size

    print(f"Backfill complete. examined={total_seen} seeded_versions={total_seeded}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Seed initial document_versions for docs missing current_hash"
    )
    ap.add_argument("--batch-size", type=int, default=500, help="rows per batch")
    ap.add_argument(
        "--db", help="Override DB URL or path (sqlite file or SQLAlchemy URL)"
    )
    args = ap.parse_args()

    # Reinitialize engine/session if a custom DB was provided
    if args.db:
        url = args.db if "://" in args.db else _sqlite_url_from_path(args.db)
        ENGINE_URL = url
        engine = create_engine(ENGINE_URL, future=True)
        SessionLocal = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, future=True
        )

    print(f"Connecting to {ENGINE_URL}")
    backfill(batch_size=args.batch_size)
