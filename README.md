# Regulatory Data Bridge

Scrape and ingest **public regulatory sources** (HTML & PDF), normalize them, detect changes/diffs, and serve them via a **FastAPI** backend. Built for downstream **RAG**, monitoring, dashboards, and **email digests**.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-blue">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-ready-brightgreen">
  <img alt="Tests" src="https://img.shields.io/badge/pytest-passing-informational">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-lightgrey">
</p>

---

## Table of Contents
- [Regulatory Data Bridge](#regulatory-data-bridge)
  - [Table of Contents](#table-of-contents)
  - [Highlights](#highlights)
  - [Repo Layout](#repo-layout)
  - [Quick Start (dev)](#quick-start-dev)
  - [API Overview](#api-overview)
    - [/changes (JSON/Markdown)](#changes-jsonmarkdown)
    - [/changes/export.csv (CSV)](#changesexportcsv-csv)
  - [Email Digests](#email-digests)
    - [Providers (Brevo / SendGrid / Gmail / SES)](#providers-brevo--sendgrid--gmail--ses)
  - [Make Targets](#make-targets)
  - [Cron Examples](#cron-examples)
  - [Configuration](#configuration)
  - [Testing](#testing)
  - [Troubleshooting](#troubleshooting)
  - [Security \& Secrets](#security--secrets)
  - [Roadmap](#roadmap)

---

## Highlights

- **Hundreds of scrapers** (federal + 50 states) under `scrapers/…`
- **Admin API**: ingest, cleanup, toggle/activate sources, bulk ops
- **HTML & PDF** pipelines, de-noise filters (drops `mailto:`, fragments, etc.)
- **Change tracking** with per-document version history
- **New:** `/changes` JSON + Markdown preview and `/changes/export.csv`
- **New:** `tools/send_digest.py` emails CSV + optional Markdown body
- **SQLite or Postgres** (via `DATABASE_URL`)

---

## Repo Layout

```

regulatory-data-bridge/
├─ app/
│  ├─ main.py               # FastAPI entry (custom docs page with CSV helper)
│  └─ routers/              # /admin, /documents, /changes
├─ tools/                   # admin/ops scripts (seed, backfill, digest)
├─ state-website-data/      # JSON lists of sources
├─ dev.db                   # default SQLite dev database
├─ requirements.txt
└─ Makefile

````

---

## Quick Start (dev)

```bash
# 0) Prereqs
# Python 3.11+, pip, venv, jq (optional)

# 1) Create venv & deps
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip wheel
# If you have a pinned set:
# pip install -r requirements.txt
pip install requests certifi

# 2) Helpful index & (optional) vacuum
sqlite3 dev.db "CREATE INDEX IF NOT EXISTS ix_doc_versions_change_time ON document_versions(change_type, fetched_at DESC);"
# sqlite3 dev.db "VACUUM;"

# 3) Run API (hot reload)
.venv/bin/uvicorn app.main:app --reload --port 8000

# 4) Verify routes
curl -s http://127.0.0.1:8000/openapi.json | jq '.paths | keys'
# Docs: http://127.0.0.1:8000/docs
````

> If `app/routers/changes.py` doesn’t show up under `/changes`, ensure `app/__init__.py` and `app/routers/__init__.py` exist and that `changes.py` defines `router = APIRouter()`.

**Seed sources (optional):**

```bash
python3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json
```

---

## API Overview

Mounted endpoints (may vary by repo):

```
/documents
/documents/export.csv
/changes
/changes/export.csv
/alerts
/sources
/admin/ingest
/admin/sources/toggle
/admin/cleanup/rrc-non-news
/admin/alerts/test
/healthz
/ready
```

### /changes (JSON/Markdown)

```http
GET /changes?jurisdiction=CO&since=2025-09-01&limit=500
GET /changes?jurisdiction=CO&format=md&group_by=source&include=diff
```

**Query params**

* `jurisdiction=CO` (required)
* `since=YYYY-MM-DD` (optional)
* `limit` (1..25,000)
* `group_by=source` (optional)
* `format=md` → returns `{ "markdown": "..." }`
* `include=diff` → includes short unified diff (when available)

### /changes/export.csv (CSV)

```http
GET /changes/export.csv?jurisdiction=CO&since=2025-09-01&limit=25000
```

> If `/changes` isn’t mounted, use `/documents/export.csv?jurisdiction=CO`.

---

## Email Digests

`tools/send_digest.py` sends a CSV attachment (from `/changes/export.csv` or fallback `/documents/export.csv`) and can **embed a Markdown preview** fetched from `/changes?format=md`.

**Examples**

```bash
# 7-day window (uses --days)
python3 tools/send_digest.py --jur CO --days 7 --to you@example.com

# Explicit start date
python3 tools/send_digest.py --jur CO --since 2025-09-01 --to you@example.com

# Incremental (persist last run date)
python3 tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to you@example.com

# Add Markdown grouping & diffs
python3 tools/send_digest.py --jur CO --days 7 --md-group-by source --md-include-diff --to you@example.com
```

**Common flags**

* `--jur CO|CA|TX …`
* Date control (pick one): `--since YYYY-MM-DD` **or** `--since-file PATH` **or** `--days N`
* `--limit 25000`
* Markdown body controls: `--md-group-by source`, `--md-include-diff`, `--no-md`
* SMTP: `--smtp-host`, `--smtp-port`, `--smtp-user`, `--smtp-pass`, `--smtp-tls`, `--from-addr`
* API key header: `--api-key` (or env `API_KEY`)

### Providers (Brevo / SendGrid / Gmail / SES)

**Brevo (Sendinblue)**

```bash
export SMTP_HOST="smtp-relay.brevo.com"
export SMTP_PORT=587
export SMTP_USER="YOUR_BREVO_SMTP_USERNAME"   # e.g., 82a...@smtp-brevo.com
export SMTP_PASS="xkeysib_..."                # Brevo SMTP key
export FROM_ADDR="RegBridge <verified@yourdomain.com>"

python3 tools/send_digest.py --jur CO --days 7 --to you@example.com --smtp-tls
```

**SendGrid**

```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASS=SG.xxxxxx
--smtp-tls
```

**Gmail**

* Requires **App Password** (2FA on). Username is the Gmail address; password is the 16-char app password.

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=<16-char app password>
--smtp-tls
```

**Amazon SES**

```bash
SMTP_HOST=email-smtp.us-west-2.amazonaws.com
SMTP_PORT=587
SMTP_USER=<SES SMTP username>
SMTP_PASS=<SES SMTP password>
--smtp-tls
```

> TLS is backed by **certifi** CA bundle in the script.

---

## Make Targets

```bash
make deps                 # venv + deps (requests, certifi)
make api                  # run FastAPI (reload)
make index                # create helpful SQLite index
make openapi-paths        # list mounted paths

# Ingest (auto-detects /admin/ingest shape via tools/admin_client.py)
make ingest JUR=CO LIMIT=3 TIMEOUT=900

# Inspect changes/CSV
make changes-json JUR=CO
make changes-csv  JUR=CO
make documents-csv JUR=CO

# Email digest (SMTP from env or flags)
make digest JUR=CO TO=client@example.com

# Brevo shortcut (uses BREVO_USER/BREVO_PASS/FROM_ADDR env)
make digest-brevo JUR=CO TO=client@example.com
```

Set once for Brevo:

```bash
export BREVO_USER="82a194001@smtp-brevo.com"
export BREVO_PASS="xkeysib_..."
export FROM_ADDR="RegBridge <verified@yourdomain.com>"
```

---

## Cron Examples

**Weekly Colorado (6:00 AM MT)**

```cron
CRON_TZ=America/Denver
0 6 * * 1 cd /ABSOLUTE/PATH/TO/regulatory-data-bridge && \
  .venv/bin/python tools/send_digest.py \
    --jur CO \
    --since-file .digest_since_co.txt \
    --to customer@example.com \
    --base http://127.0.0.1:8000 \
    --md-group-by source \
  >> logs/digest_co.log 2>&1
```

**Weekly via Make + Brevo**

```cron
CRON_TZ=America/Denver
0 6 * * 1 BREVO_USER=82a194001@smtp-brevo.com BREVO_PASS=xkeysib_... \
  FROM_ADDR="RegBridge <verified@yourdomain.com>" \
  cd /ABSOLUTE/PATH/TO/regulatory-data-bridge && \
  make digest-brevo JUR=CO TO=customer@example.com \
  >> logs/digest_co.log 2>&1
```

**Daily smoke @ 7:00 AM**

```cron
CRON_TZ=America/Denver
0 7 * * * cd /ABSOLUTE/PATH/TO/regulatory-data-bridge && \
  .venv/bin/python tools/send_digest.py \
    --jur CO --days 1 --to you@example.com \
    --base http://127.0.0.1:8000 --limit 2000 --md-group-by source \
  >> logs/digest_co_smoke.log 2>&1
```

---

## Configuration

* **Database**

  * Dev: SQLite `dev.db`
  * Prod: set `DATABASE_URL=postgresql+psycopg://user:pass@host/db`

* **CORS**

  * `CORS_ALLOWED_ORIGINS` (comma-separated), used by `app.main.py`

* **Docs CSV button**

  * `CSV_DEFAULT_URL` (e.g., `/changes/export.csv?jurisdiction=CO&since=2025-09-01`)

* **Tools base URL**

  * `API_BASE` (default `http://127.0.0.1:8000`)

---

## Testing

```bash
pytest -v
# focused examples
pytest -v tests/test_export_csv.py
```

---

## Troubleshooting

* **`/changes` not found**

  * Ensure `app/routers/changes.py` is importable and defines `router = APIRouter()`
  * `touch app/__init__.py app/routers/__init__.py`
  * Restart API, then `make openapi-paths`

* **`/admin/ingest` timeouts**

  * Start tiny: `make ingest JUR=CO LIMIT=1 TIMEOUT=900`
  * Avoid `--force` for first passes; consider queueing long jobs in future

* **SMTP TLS errors**

  * Script uses **certifi**; install with `pip install certifi`
  * For port **587**, pass `--smtp-tls`. For **465**, omit (implicit SSL)

* **Brevo 535 Authentication failed**

  * Username must be your **Brevo SMTP username** (`…@smtp-brevo.com`)
  * Password must be the **SMTP key** (`xkeysib_…`)
  * Verify the **From** address is a verified sender/domain

---

## Security & Secrets

* **Never commit real secrets.** Keep local env files out of git:

  ```gitignore
  .env
  .env.local
  .env.*.local
  *.key
  ```

* Use placeholders in `.env.example` (e.g., `SMTP_PASS=__SET_IN_ENV__`).

* If GitHub **Push Protection** blocks a push:

  1. Rotate the leaked key with your provider.
  2. Rewrite the offending commit(s) (interactive rebase or `git filter-repo`).
  3. Force-push with lease.

* Optional pre-commit guard against Brevo keys:

  ```bash
  mkdir -p .git/hooks
  cat > .git/hooks/pre-commit <<'SH'
  #!/usr/bin/env bash
  if git diff --cached -G'xkeysib[-_]|xsmtpsib[-_]' --name-only | grep -q .; then
    echo "❌ Found something that looks like a Brevo SMTP key in staged changes."
    exit 1
  fi
  SH
  chmod +x .git/hooks/pre-commit
  ```

---

## Roadmap

* Wave-by-wave state hardening (filters, dedupe, PDF robustness)
* Job queue for long ingests; `/admin/jobs` status
* Web UI scaffold (Vite + React) for changes browsing/export/email
* Metrics & `/health` expansion (docs/sec, errors, last run)
* Postgres schema + migrations for production

