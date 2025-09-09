#!/usr/bin/env python3
"""
change_tracker.py — Compute hashes, track versions, and record diffs for documents.

Place at: app/services/change_tracker.py  (or keep current location and imports)
Run from: your app context (called from scrapers/ingesters with a DB session).

What this does:
  - Normalizes extracted text and computes a stable SHA-1 content hash.
  - Seeds initial version rows for legacy documents missing current_hash.
  - Appends new DocumentVersion rows when content changes (ADDED/UPDATED/REMOVED).
  - Maintains document tracking fields:
      current_hash, first_seen_at, last_seen_at, last_changed_at.
  - Provides optional unified diff summary helper (not persisted by default).

Key functions:
  - record_version(db, doc, extracted_text, title) -> "ADDED" | "UPDATED" | "NOCHANGE"
  - record_removed(db, doc, reason="removed") -> "REMOVED"
  - seed_if_missing(db, doc, text=None, title=None) -> "ADDED" | "SEEDED-DOC" | "SKIP"

Why it matters:
  - Enables robust change tracking across re-ingests and edits.
  - Keeps a historical timeline in document_versions for audit and diffing.
  - Safely seeds legacy rows so downstream tools (exports/alerts) have hashes.

Examples (pseudo-usage):
  from app.services.change_tracker import record_version
  # after fetching and extracting text:
  status = record_version(db, doc, extracted_text=page_text, title=page_title)
  if status in ("ADDED", "UPDATED"):
      db.commit()

  # seeding legacy rows missing current_hash:
  for doc in db.query(Document).filter(Document.current_hash.is_(None)):
      seed_if_missing(db, doc, text=doc.text, title=doc.title)
  db.commit()

Notes:
  - Hash basis prefers extracted_text; if absent, uses "title\\nurl" for stability.
  - SNAPSHOT_MAX_CHARS limits stored snapshot size (default 20k chars).
"""

from __future__ import annotations
import hashlib
from datetime import datetime
from difflib import unified_diff
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

# --- Model imports (support both singular/plural module names) ---
try:
    from app.db.model import Document, DocumentVersion  # your current file path
except Exception:  # pragma: no cover
    from app.db.models import Document, DocumentVersion  # fallback if repo uses plural


SNAPSHOT_MAX_CHARS = 20_000


# -----------------------
# Utilities
# -----------------------
def normalize_text(s: Optional[str]) -> str:
    """Normalize text before hashing/snapshotting."""
    if not s:
        return ""
    # normalize newlines and trim trailing whitespace lines
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()


def compute_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def diff_summary(prev: Optional[str], curr: Optional[str], max_lines: int = 12) -> str:
    prev_s = normalize_text(prev).splitlines()
    curr_s = normalize_text(curr).splitlines()
    lines = list(unified_diff(prev_s, curr_s, lineterm=""))
    if not lines:
        return ""
    head = lines[:max_lines]
    if len(lines) > max_lines:
        head.append(f"... (+{len(lines)-max_lines} more)")
    return "\n".join(head)


# -----------------------
# Core: record_version
# -----------------------
def record_version(
    db: Session,
    doc: Document,
    *,
    extracted_text: Optional[str],
    title: Optional[str],
) -> str:
    """
    Compare current_hash vs new hash; if changed, append a version row and update doc fields.
    Returns: 'ADDED' | 'UPDATED' | 'NOCHANGE'
    """
    now = datetime.utcnow()

    # Prefer extracted_text; if missing, fall back to a stable basis so we can seed
    basis_text = normalize_text(extracted_text) or normalize_text(f"{title or doc.title}\n{doc.url}")
    new_hash = compute_hash(basis_text)

    # First time seeing this doc with content
    if not getattr(doc, "current_hash", None):
        doc.current_hash = new_hash
        doc.first_seen_at = now
        doc.last_seen_at = now
        doc.last_changed_at = now

        v = DocumentVersion(
            doc_id=doc.id,
            version_no=1,
            content_hash=new_hash,
            title=title or getattr(doc, "title", None),
            snapshot=basis_text[:SNAPSHOT_MAX_CHARS],
            change_type="ADDED",
        )
        db.add(v)
        return "ADDED"

    # Subsequent fetch
    doc.last_seen_at = now
    if doc.current_hash == new_hash:
        return "NOCHANGE"

    # Changed → next version number
    last_no = (
        db.query(DocumentVersion.version_no)
        .filter(DocumentVersion.doc_id == doc.id)
        .order_by(DocumentVersion.version_no.desc())
        .first()
    )
    next_no = (last_no[0] if last_no else 0) + 1

    # Optional: generate a short diff (not stored by default)
    # prev_text = (
    #     db.query(DocumentVersion.snapshot)
    #     .filter(DocumentVersion.doc_id == doc.id)
    #     .order_by(DocumentVersion.version_no.desc())
    #     .limit(1)
    #     .scalar()
    # )
    # summary = diff_summary(prev_text, basis_text)

    v = DocumentVersion(
        doc_id=doc.id,
        version_no=next_no,
        content_hash=new_hash,
        title=title or getattr(doc, "title", None),
        snapshot=basis_text[:SNAPSHOT_MAX_CHARS],
        change_type="UPDATED",
    )
    db.add(v)

    doc.current_hash = new_hash
    doc.last_changed_at = now
    if title and getattr(doc, "title", None) != title:
        doc.title = title

    return "UPDATED"


# -----------------------
# Optional helpers
# -----------------------
def record_removed(db: Session, doc: Document, *, reason: str = "removed") -> str:
    """
    Append a REMOVED version (e.g., source 404s or is deliberately retired).
    Does not change current_hash; sets last_seen_at and last_changed_at.
    """
    now = datetime.utcnow()
    # next version number
    last_no = (
        db.query(DocumentVersion.version_no)
        .filter(DocumentVersion.doc_id == doc.id)
        .order_by(DocumentVersion.version_no.desc())
        .first()
    )
    next_no = (last_no[0] if last_no else 0) + 1

    v = DocumentVersion(
        doc_id=doc.id,
        version_no=next_no,
        content_hash=doc.current_hash or compute_hash(f"{doc.title}\n{doc.url}"),
        title=doc.title,
        snapshot=f"(Document marked removed: {reason})",
        change_type="REMOVED",
    )
    db.add(v)

    doc.last_seen_at = now
    doc.last_changed_at = now
    return "REMOVED"


def seed_if_missing(
    db: Session,
    doc: Document,
    *,
    text: Optional[str] = None,
    title: Optional[str] = None,
) -> str:
    """
    One-time seeding helper for existing rows without current_hash.
    Uses text if provided, otherwise title+url.
    """
    if getattr(doc, "current_hash", None):
        return "SKIP"

    basis = normalize_text(text) or normalize_text(f"{title or doc.title}\n{doc.url}")
    h = compute_hash(basis)
    now = datetime.utcnow()

    # If a version already exists, only fill doc fields
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
        return "SEEDED-DOC"

    # Create initial version
    doc.current_hash = h
    doc.first_seen_at = now
    doc.last_seen_at = now
    doc.last_changed_at = now

    v = DocumentVersion(
        doc_id=doc.id,
        version_no=1,
        content_hash=h,
        title=title or doc.title,
        snapshot=basis[:SNAPSHOT_MAX_CHARS],
        change_type="ADDED",
    )
    db.add(v)
    return "ADDED"
