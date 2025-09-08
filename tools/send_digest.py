#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Send a digest email with:
  1) CSV attachment of recent regulatory changes
  2) Optional Markdown preview in the email body (/changes?format=md)

Features
- Works for ANY state via --jur (e.g., CO, CA, TX)
- Prefer /changes/export.csv; fall back to /documents/export.csv if needed
- Date controls:
    * --since YYYY-MM-DD
    * --since-file <path>  (persists last-sent date and updates to today on success)
    * --days N             (shorthand: today - N days; ignored if --since or --since-file resolves)
- SMTP with TLS/SSL using certifi CA bundle (Brevo/SendGrid/Gmail/SES)
- Optional X-API-Key via --api-key (or env API_KEY)
- Prints JSON status to stdout (cron/tee friendly)
"""

import argparse
import os
import sys
import json
import smtplib
import ssl
import datetime
import io
import csv
import html
from typing import Optional, Tuple, List

import requests
import certifi
from email.message import EmailMessage

# ---------- Defaults / ENV ----------
ENV = os.environ
DEFAULT_BASE = ENV.get("API_BASE", "http://127.0.0.1:8000")

DEF_SMTP_HOST = ENV.get("SMTP_HOST", "smtp.gmail.com")
DEF_SMTP_PORT = int(ENV.get("SMTP_PORT", "587"))
DEF_SMTP_USER = ENV.get("SMTP_USER", "")
DEF_SMTP_PASS = ENV.get("SMTP_PASS", "")
DEF_SMTP_TLS  = ENV.get("SMTP_TLS", "true").lower() in ("1", "true", "yes", "on")
DEF_FROM_ADDR = ENV.get("FROM_ADDR", "no-reply@localhost")
DEF_API_KEY   = ENV.get("API_KEY", None)  # optional X-API-Key for your API


# ---------- Helpers ----------
def today_iso() -> str:
    return datetime.date.today().isoformat()

def read_since_from_file(path: Optional[str]) -> Optional[str]:
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            val = f.readline().strip()
        datetime.date.fromisoformat(val)  # validate
        return val
    except Exception:
        return None

def write_since_file(path: str, date_str: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(date_str + "\n")

def fetch_openapi(base: str, api_key: Optional[str]) -> dict:
    headers = {"X-API-Key": api_key} if api_key else {}
    r = requests.get(f"{base}/openapi.json", headers=headers, timeout=(10, 30))
    r.raise_for_status()
    return r.json()

def route_exists(spec: dict, path: str) -> bool:
    return path in spec.get("paths", {})

def get_changes_csv(base: str, jur: str, since: Optional[str], limit: int, api_key: Optional[str]) -> Tuple[bytes, str, str]:
    """
    Returns (csv_bytes, endpoint_used, url_used)
    Tries /changes/export.csv first; falls back to /documents/export.csv if not present.
    """
    spec = fetch_openapi(base, api_key)
    headers = {"X-API-Key": api_key} if api_key else {}
    qs_since = f"&since={since}" if since else ""

    if route_exists(spec, "/changes/export.csv"):
        url = f"{base}/changes/export.csv?jurisdiction={jur.upper()}{qs_since}&limit={limit}"
        ep  = "/changes/export.csv"
    else:
        # Fallback; may not support 'since'
        url = f"{base}/documents/export.csv?jurisdiction={jur.upper()}&limit={limit}"
        ep  = "/documents/export.csv"

    r = requests.get(url, headers=headers, timeout=(10, 120))
    r.raise_for_status()
    return r.content, ep, url

def get_changes_markdown(
    base: str,
    jur: str,
    since: Optional[str],
    group_by: Optional[str],
    include_diff: bool,
    limit: int,
    api_key: Optional[str],
) -> Optional[str]:
    """
    Fetches server-rendered markdown from /changes?format=md.
    Returns markdown text or None if the route isn't available.
    """
    spec = fetch_openapi(base, api_key)
    if not route_exists(spec, "/changes"):
        return None

    headers = {"X-API-Key": api_key} if api_key else {}
    params = {
        "jurisdiction": jur.upper(),
        "format": "md",
        "limit": str(limit),
    }
    if since:
        params["since"] = since
    if group_by in ("source",):
        params["group_by"] = group_by
    if include_diff:
        params["include"] = "diff"

    r = requests.get(f"{base}/changes", headers=headers, params=params, timeout=(10, 60))
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "markdown" in data:
        return data["markdown"]
    if isinstance(data, str):
        return data
    return None

def count_csv_rows(csv_bytes: bytes) -> int:
    try:
        text = csv_bytes.decode("utf-8", errors="ignore")
        buf = io.StringIO(text)
        reader = csv.reader(buf)
        rows = sum(1 for _ in reader)
        return max(0, rows - 1)  # minus header
    except Exception:
        return 0

def make_tls_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())

def build_html_body(plain_intro: str, md: Optional[str]) -> str:
    intro_html = "<p>" + "<br/>".join(html.escape(line) for line in plain_intro.splitlines()) + "</p>"
    if not md:
        return f"<html><body>{intro_html}</body></html>"
    md_html = (
        "<h3>Markdown preview</h3>"
        "<pre style='white-space:pre-wrap;font-family:ui-monospace,Menlo,Consolas,monospace'>"
        f"{html.escape(md)}"
        "</pre>"
    )
    return f"<html><body>{intro_html}{md_html}</body></html>"

def send_email_with_attachment(
    to_addrs: List[str],
    subject: str,
    body_text_intro: str,
    body_md: Optional[str],
    attach_name: str,
    attach_bytes: bytes,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    smtp_tls: bool,
    from_addr: str,
) -> None:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject

    # Plain text + optional Markdown
    if body_md:
        msg.set_content(body_text_intro + "\n\n---\nMarkdown preview\n\n" + body_md)
    else:
        msg.set_content(body_text_intro)

    # HTML alternative
    html_part = build_html_body(body_text_intro, body_md)
    msg.add_alternative(html_part, subtype="html")

    # CSV attachment
    msg.add_attachment(attach_bytes, maintype="text", subtype="csv", filename=attach_name)

    # TLS/SSL with certifi
    if smtp_port == 465:
        ctx = make_tls_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as s:
            if smtp_user:
                s.login(smtp_user, smtp_pass)
            s.send_message(msg)
        return

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        if smtp_tls:
            ctx = make_tls_context()
            s.starttls(context=ctx)
        if smtp_user:
            s.login(smtp_user, smtp_pass)
        s.send_message(msg)


# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser(description="Send digest email with CSV attachment + optional Markdown preview.")
    ap.add_argument("--jur", required=True, help="Jurisdiction/state code (e.g., CO, CA, TX)")
    ap.add_argument("--to", required=True, nargs="+", help="Recipient email(s)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="API base URL (default: %(default)s)")

    # Date controls
    ap.add_argument("--since", default=None, help="YYYY-MM-DD explicit since date")
    ap.add_argument("--since-file", default=None, help="Path to persist last-sent date; updated to today on success")
    ap.add_argument("--days", type=int, default=None,
                    help="Shorthand: use today - N days as --since (ignored if --since/--since-file resolves)")

    ap.add_argument("--subject", default=None, help="Email subject override")
    ap.add_argument("--limit", type=int, default=25000, help="Max CSV rows to request (default: %(default)s)")
    ap.add_argument("--api-key", default=DEF_API_KEY, help="Optional X-API-Key header (or set env API_KEY)")

    # Markdown embedding controls
    ap.add_argument("--no-md", dest="embed_md", action="store_false", help="Disable Markdown preview in body")
    ap.add_argument("--md-group-by", choices=["source"], default=None, help="Group markdown by 'source'")
    ap.add_argument("--md-include-diff", action="store_true", help="Include short diff blocks in markdown preview")

    # SMTP
    ap.add_argument("--smtp-host", default=DEF_SMTP_HOST)
    ap.add_argument("--smtp-port", type=int, default=DEF_SMTP_PORT)
    ap.add_argument("--smtp-user", default=DEF_SMTP_USER)
    ap.add_argument("--smtp-pass", default=DEF_SMTP_PASS)
    ap.add_argument("--smtp-tls", action="store_true", default=DEF_SMTP_TLS,
                    help="Use STARTTLS when port is not 465 (default based on env SMTP_TLS)")
    ap.add_argument("--from-addr", default=DEF_FROM_ADDR)

    args = ap.parse_args()

    jur = args.jur.upper()

    # Resolve since → CLI > since-file > --days
    since = args.since or read_since_from_file(args.since_file)
    if args.days and not since:
        since = (datetime.date.today() - datetime.timedelta(days=args.days)).isoformat()

    # Fetch CSV
    try:
        csv_bytes, ep, url_used = get_changes_csv(args.base, jur, since, args.limit, args.api_key)
    except Exception as e:
        print(json.dumps({"ok": False, "step": "fetch_csv", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

    rows = count_csv_rows(csv_bytes)

    # Optionally fetch Markdown preview
    md_text = None
    md_included = False
    if args.embed_md:
        try:
            md_text = get_changes_markdown(
                base=args.base,
                jur=jur,
                since=since,
                group_by=args.md_group_by,
                include_diff=args.md_include_diff,
                limit=min(args.limit, 2000),  # keep preview compact
                api_key=args.api_key,
            )
            md_included = bool(md_text)
        except Exception as e:
            md_text = None
            md_included = False
            print(json.dumps({"ok": True, "warning": f"failed to fetch markdown preview: {e}"}))

    subject = args.subject or f"{jur} regulatory changes – {today_iso()} (rows: {rows})"
    intro = (
        f"Hi,\n\n"
        f"Attached are the latest {jur} regulatory changes as a CSV.\n\n"
        f"Endpoint: {ep}\n"
        f"URL: {url_used}\n"
        f"Since: {since or 'N/A'}\n"
        f"Rows: {rows}\n"
    )
    attach_name = f"{jur}_changes_{today_iso()}.csv"

    # Send email
    try:
        send_email_with_attachment(
            to_addrs=args.to,
            subject=subject,
            body_text_intro=intro,
            body_md=md_text,
            attach_name=attach_name,
            attach_bytes=csv_bytes,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            smtp_user=args.smtp_user,
            smtp_pass=args.smtp_pass,
            smtp_tls=args.smtp_tls,
            from_addr=args.from_addr,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "step": "send_email", "error": str(e)}), file=sys.stderr)
        sys.exit(1)

    # Update since-file to today on success
    since_file_updated = False
    if args.since_file:
        try:
            write_since_file(args.since_file, today_iso())
            since_file_updated = True
        except Exception as e:
            print(json.dumps({"ok": True, "warning": f"failed to update since-file: {e}"}))

    print(json.dumps({
        "ok": True,
        "jur": jur,
        "to": args.to,
        "rows": rows,
        "endpoint": ep,
        "url": url_used,
        "since": since,
        "since_file": args.since_file,
        "since_file_updated": since_file_updated,
        "markdown_included": md_included
    }, indent=2))


if __name__ == "__main__":
    main()
