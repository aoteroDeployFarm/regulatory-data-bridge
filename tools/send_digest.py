#!/usr/bin/env python3
"""
Send a digest of document changes to email and/or Slack.

Examples:
  # Print last 7 days of CO changes
  python3 tools/send_digest.py --jur CO --days 7

  # Email yesterday's CO changes (needs SMTP_* envs)
  SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=you@gmail.com SMTP_PASS='app_pw' SMTP_FROM=you@gmail.com \
  python3 tools/send_digest.py --jur CO --days 1 --to customer@example.com

  # Slack (Incoming Webhook)
  python3 tools/send_digest.py --jur CO --days 1 --slack https://hooks.slack.com/services/XXX/YYY/ZZZ

  # Incremental mode: only send changes since the last run (state stored in a file)
  python3 tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to customer@example.com
"""
from __future__ import annotations

import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API = os.getenv("API_BASE", "http://127.0.0.1:8000")


def _read_since(since_file: str) -> Optional[str]:
    try:
        with open(since_file, "r", encoding="utf-8") as f:
            s = f.read().strip()
            return s or None
    except FileNotFoundError:
        return None


def _write_since(since_file: str, iso_timestamp: str) -> None:
    tmp = since_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(iso_timestamp)
    os.replace(tmp, since_file)


def _iso_now() -> str:
    # ISO8601 without timezone; matches FastAPI's default JSON for naive datetimes
    return datetime.utcnow().isoformat(timespec="seconds")


def fetch_changes(jur: str, *, since_iso: Optional[str], days: Optional[int], limit: int = 2000) -> List[dict]:
    params = {"jurisdiction": jur.upper(), "limit": str(limit)}
    if since_iso:
        params["since"] = since_iso
    elif days is not None:
        since_dt = datetime.utcnow() - timedelta(days=days)
        params["since"] = since_dt.strftime("%Y-%m-%d")
    # else: API defaults to 7 days
    url = f"{API}/changes?{urlencode(params)}"
    with urlopen(url) as r:
        return json.load(r)


def build_markdown(jur: str, rows: List[dict]) -> str:
    if not rows:
        return f"**{jur}** — no changes in the selected window."
    lines = [f"## {jur} changes ({len(rows)})"]
    for r in rows:
        ts = str(r.get("fetched_at", ""))[:19].replace("T", " ")
        title = (r.get("title") or "(untitled)").strip()
        url = r.get("url") or ""
        lines.append(f"- **{r['change_type']}** · {ts} · [{title}]({url})")
    return "\n".join(lines)


def latest_timestamp(rows: List[dict]) -> Optional[str]:
    best: Optional[datetime] = None
    best_raw: Optional[str] = None
    for r in rows:
        raw = str(r.get("fetched_at", "")).strip()
        if not raw:
            continue
        # try a few parse shapes
        parsed: Optional[datetime] = None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        if not parsed:
            continue
        if best is None or parsed > best:
            best, best_raw = parsed, raw
    return best_raw


def send_email(md: str, to_addr: str, subject: str):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM", user or "no-reply@example.com")

    msg = MIMEText(md, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as s:
        s.starttls()
        if user and pwd:
            s.login(user, pwd)
        s.sendmail(from_addr, [to_addr], msg.as_string())


def send_slack(md: str, webhook: str):
    body = json.dumps({"text": md}).encode("utf-8")
    req = Request(webhook, data=body, headers={"Content-Type": "application/json"})
    urlopen(req).read()


def main():
    import argparse

    ap = argparse.ArgumentParser(description="Send a digest of document changes.")
    ap.add_argument("--jur", required=True, help="State code, e.g. CO")
    ap.add_argument("--days", type=int, default=7, help="Lookback window in days (ignored if --since-file provided)")
    ap.add_argument("--limit", type=int, default=2000, help="Max rows to retrieve")
    ap.add_argument("--to", help="Email recipient address")
    ap.add_argument("--slack", help="Slack Incoming Webhook URL")
    ap.add_argument("--since-file", help="Path to a file storing the last sent timestamp (incremental mode)")
    args = ap.parse_args()

    since_iso = _read_since(args.since_file) if args.since_file else None
    rows = fetch_changes(args.jur, since_iso=since_iso, days=(None if since_iso else args.days), limit=args.limit)
    md = build_markdown(args.jur, rows)
    subj = f"[Regulatory Bridge] {args.jur.upper()} changes ({'since '+since_iso if since_iso else f'last {args.days}d'}: {len(rows)})"

    if args.to:
        send_email(md, args.to, subj)
        print(f"email sent to {args.to}")
    if args.slack:
        send_slack(md, args.slack)
        print("slack sent")
    if not args.to and not args.slack:
        print(md)

    # Update since-file to latest timestamp (or now if nothing returned)
    if args.since_file:
        new_since = latest_timestamp(rows) or _iso_now()
        _write_since(args.since_file, new_since)
        print(f"since-file updated -> {args.since_file}: {new_since}")


if __name__ == "__main__":
    main()
