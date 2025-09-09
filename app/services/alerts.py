#!/usr/bin/env python3
"""
alerts.py — Simple keyword-alert matching + email notifications.

Place at: app/services/alerts.py
Used by: admin routes, cron jobs, or CLI utilities.

What this does:
  - Scans active Alert rows and finds recent Document matches by keyword
    (title/text ILIKE) and optional jurisdiction.
  - Sends plain-text email notifications for each match via SMTP.

Why it matters:
  - Provides an MVP alerting loop so users get notified when new content matches
    their saved keywords.

Environment (SMTP):
  - SMTP_HOST (default: "localhost")
  - SMTP_PORT (default: 25)
  - SMTP_FROM (default: "alerts@regulatorydatabridge.com")

Public functions:
  - find_matches(db) -> list[(Alert, Document)]
  - send_email(subject, body, to_addr) -> None
  - notify(db, to_addr) -> None        # find & send emails for each match

Examples:
  from app.db.session import SessionLocal
  from app.services.alerts import notify

  with SessionLocal() as db:
      notify(db, to_addr="ops@example.com")
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import List

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from ..db.models import Alert, Document


def find_matches(db: Session):
    """
    Return a list of (Alert, Document) tuples for active alerts.

    Matching logic:
      - Document.title ILIKE '%keyword%' OR Document.text ILIKE '%keyword%'
      - If Alert.jurisdiction is set, require documents to match it
      - Up to 20 most recent docs per alert
    """
    alerts = db.execute(select(Alert).where(Alert.active == True)).scalars().all()  # noqa: E712
    matched: list[tuple[Alert, Document]] = []
    for a in alerts:
        like = f"%{a.keyword}%"
        q = (
            select(Document)
            .where(
                and_(
                    or_(Document.title.ilike(like), Document.text.ilike(like)),
                    (Document.jurisdiction == a.jurisdiction) if a.jurisdiction else True,
                )
            )
            .order_by(Document.id.desc())
            .limit(20)
        )
        for doc in db.execute(q).scalars():
            matched.append((a, doc))
    return matched


def send_email(subject: str, body: str, to_addr: str) -> None:
    """
    Send a plain-text email using SMTP settings from environment.

    Env:
      SMTP_HOST, SMTP_PORT, SMTP_FROM
    """
    host = os.getenv("SMTP_HOST", "localhost")
    port = int(os.getenv("SMTP_PORT", "25"))
    sender = os.getenv("SMTP_FROM", "alerts@regulatorydatabridge.com")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(host, port) as s:
        s.send_message(msg)


def notify(db: Session, to_addr: str) -> None:
    """
    Find matches for all active alerts and send an email per match to `to_addr`.
    """
    for alert, doc in find_matches(db):
        subject = f"[RDB] New match: {alert.keyword}"
        body = f"{doc.title}\n{doc.url}\nJurisdiction: {doc.jurisdiction or '-'}"
        send_email(subject, body, to_addr)
