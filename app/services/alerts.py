from __future__ import annotations
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from ..db.models import Alert, Document
import smtplib, os
from email.message import EmailMessage

def find_matches(db: Session):
    alerts = db.execute(select(Alert).where(Alert.active == True)).scalars().all()
    matched: list[tuple[Alert, Document]] = []
    for a in alerts:
        like = f"%{a.keyword}%"
        q = select(Document).where(
            and_(
                or_(Document.title.ilike(like), Document.text.ilike(like)),
                (Document.jurisdiction == a.jurisdiction) if a.jurisdiction else True
            )
        ).order_by(Document.id.desc()).limit(20)
        for doc in db.execute(q).scalars():
            matched.append((a, doc))
    return matched

def send_email(subject: str, body: str, to_addr: str):
    # MVP: SMTP from env
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

def notify(db: Session, to_addr: str):
    for alert, doc in find_matches(db):
        subject = f"[RDB] New match: {alert.keyword}"
        body = f"{doc.title}\n{doc.url}\nJurisdiction: {doc.jurisdiction or '-'}"
        send_email(subject, body, to_addr)
