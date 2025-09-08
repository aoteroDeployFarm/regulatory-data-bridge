# Regulatory Data Bridge

Scrape and ingest **public regulatory sources** (HTML & PDF), normalize them, detect changes/diffs, and serve them via a **FastAPI** backend. Built for downstream **RAG** (ChatGPT/Gemini), monitoring, dashboards, and **alerts**.

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
    - [0) Prereqs](#0-prereqs)
    - [1) Fresh virtualenv](#1-fresh-virtualenv)
    - [2) Fix stdlib name-clash (one-time)](#2-fix-stdlib-name-clash-one-time)
    - [3) Seed sources](#3-seed-sources)
    - [4) Run the API](#4-run-the-api)
  - [Activate \& Run All 50 States](#activate--run-all-50-states)
    - [A) Activate all sources](#a-activate-all-sources)
    - [B) Ingest everything (cached where possible)](#b-ingest-everything-cached-where-possible)
  - [Admin API](#admin-api)
  - [Documents API](#documents-api)
  - [Change Tracking](#change-tracking)
    - [DB migration](#db-migration)
    - [Backfill existing docs](#backfill-existing-docs)
    - [Changes API](#changes-api)
    - [Customer digests \& notifications](#customer-digests--notifications)
  - [Scripts \& Make Targets](#scripts--make-targets)
  - [Configuration](#configuration)
  - [Testing](#testing)
  - [Troubleshooting](#troubleshooting)
  - [Roadmap](#roadmap)

---

## Highlights

* **Hundreds of scrapers** (federal + all 50 states) organized under `scrapers/…`
* **Admin API**: ingest, cleanup, toggle/activate sources, bulk ops
* **Filters** to drop nav/noise links (`mailto`, `tel`, fragments, “Home”, etc.)
* **HTML & PDF** pipelines (BeautifulSoup + PDF extraction)
* **Per-source caching** and optional `force` refresh
* **Change tracking** with version history per document
* **CSV export** for downstream analytics and BI tools

---

## Repo Layout

```

regulatory-data-bridge/
app/
main.py           # FastAPI entry
routers/          # /admin, /documents, /changes
services/         # ingest orchestration, change tracker
db/               # models, migrations, session helpers
tools/              # admin/ops scripts (seed, upsert, backfill, digest)
state-website-data/ # JSON lists of sources
requirements.txt
dev.db              # default SQLite dev database

````

---

## Quick Start (dev)

### 0) Prereqs

* Python **3.11+**
* `pip`, `venv`
* (optional) `jq` for pretty JSON in shell

### 1) Fresh virtualenv

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
python -m pip install -U pip
pip install -r requirements.txt
````

### 2) Fix stdlib name-clash (one-time)

If a top-level `html.py` exists, rename it (it shadows Python’s `html` stdlib):

```bash
mv html.py html_utils.py
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### 3) Seed sources

Register sources into the DB (reads from `./state-website-data/state-website-data.json`):

```bash
python3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json
```

### 4) Run the API

```bash
uvicorn app.main:app --reload --port 8000
# http://127.0.0.1:8000/docs
```

---

## Activate & Run All 50 States

### A) Activate all sources

**Option 1 — bulk toggle endpoint (if present):**

```bash
curl -s -X POST "http://127.0.0.1:8000/admin/sources/activate-all" | jq
```

**Option 2 — tiny Python one-liner (always works):**

```bash
PYTHONPATH=. python - <<'PY'
from app.db.session import get_engine, get_session
from app.db.model import Source
engine = get_engine()
with get_session(engine) as db:
    n = db.query(Source).update({Source.active: True})
    db.commit()
    print(f"Activated {n} sources.")
PY
```

### B) Ingest everything (cached where possible)

```bash
curl -s -X POST "http://127.0.0.1:8000/admin/ingest" | jq
```

**Force a fresh pass (ignore cache):**

```bash
curl -s -X POST "http://127.0.0.1:8000/admin/ingest?force=true" | jq
```

---

## Admin API

* **Ingest all active sources**
  `POST /admin/ingest` → `{ ok, count, updated, failed, ... }`

* **Toggle a source**
  `POST /admin/sources/toggle?name=...&active=true|false`

* **Cleanup helpers** (drop noisy links/titles):

  * `POST /admin/cleanup/fragment-only`
  * `POST /admin/cleanup/trailing-hash`
  * `POST /admin/cleanup/non-http`
  * `POST /admin/cleanup/titles-exact?title=Home`

---

## Documents API

* **Search**

  ```bash
  curl -s "http://127.0.0.1:8000/documents?limit=20&jurisdiction=TX" | jq .
  ```

* **Export CSV**

  ```bash
  curl -s "http://127.0.0.1:8000/documents/export.csv?jurisdiction=CO&limit=500" -o out_CO.csv
  ```

---

## Change Tracking

The app stores a **version row** each time a document is first seen or its content changes. Fields on `documents`:

* `current_hash`, `first_seen_at`, `last_seen_at`, `last_changed_at`

Version table: `document_versions (doc_id, version_no, content_hash, title, snapshot, change_type, fetched_at)`.

### DB migration

```bash
PYTHONPATH=. python3 app/db/migrations/001_change_tracking.py
```

### Backfill existing docs

If you had documents before enabling change tracking:

```bash
PYTHONPATH=. python3 tools/backfill_versions.py
# or point at a different DB:
# PYTHONPATH=. python3 tools/backfill_versions.py --db dev.db
```

### Changes API

**JSON (Colorado, last 7 days by default):**

```bash
curl -s "http://127.0.0.1:8000/changes?jurisdiction=CO" | jq .
```

**CSV (Colorado, custom window):**

```bash
curl -s "http://127.0.0.1:8000/changes/export.csv?jurisdiction=CO&since=$(date -v-14d +%F)" -o co_changes_14d.csv
# Linux: $(date -d '14 days ago' +%F)
```

### Customer digests & notifications

Use the digest tool to send email/Slack summaries. It talks to `/changes`.

**Print to terminal (7 days):**

```bash
python3 tools/send_digest.py --jur CO --days 7
```

**Email (1 day window):**

```bash
SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=you@gmail.com SMTP_PASS='app_pw' SMTP_FROM=you@gmail.com \
python3 tools/send_digest.py --jur CO --days 1 --to customer@example.com
```

**Slack (Incoming Webhook):**

```bash
python3 tools/send_digest.py --jur CO --days 1 --slack https://hooks.slack.com/services/XXX/YYY/ZZZ
```

**Incremental mode (`--since-file`)**
Only send *new* changes since the last run; the tool stores the last sent timestamp in a file:

```bash
python3 tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to customer@example.com
# On subsequent runs, it will pick up only newer rows and update the file.
```

**Cron (nightly at 01:40)**

*Email digest for CO (last 1 day):*

```cron
40 1 * * * /bin/bash -lc 'cd /path/to/repo && . .venv/bin/activate && \
SMTP_HOST=smtp.gmail.com SMTP_PORT=587 SMTP_USER=you@gmail.com SMTP_PASS="app_pw" SMTP_FROM=you@gmail.com \
python3 tools/send_digest.py --jur CO --days 1 --to customer@example.com >> logs/digest.log 2>&1'
```

*Incremental digest (since last run):*

```cron
15 7 * * * /bin/bash -lc 'cd /path/to/repo && . .venv/bin/activate && \
python3 tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to customer@example.com >> logs/digest.log 2>&1'
```

*Set API base once (optional):*

```bash
export API_BASE=http://127.0.0.1:8000
```

---

## Scripts & Make Targets

Run scripts as modules or set `PYTHONPATH=.` when executing from repo root.

```makefile
install:
\tpip install -r requirements.txt

api:
\tuvicorn app.main:app --reload --port 8000

seed:
\tpython3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json

activate-all:
\tPYTHONPATH=. python - <<'PY'\nfrom app.db.session import get_engine, get_session\nfrom app.db.model import Source\nengine = get_engine()\nwith get_session(engine) as db:\n    n = db.query(Source).update({Source.active: True})\n    db.commit()\n    print(f"Activated {n} sources.")\nPY

ingest:
\tcurl -s -X POST "http://127.0.0.1:8000/admin/ingest" | jq

backfill-versions:
\tPYTHONPATH=. python3 tools/backfill_versions.py

digest-co-incremental:
\tpython3 tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to customer@example.com
```

---

## Configuration

* **Settings**: environment variables in `.env` if you use one (CORS, timeouts, etc.)
* **Database**: default `dev.db` (SQLite) for dev; use `DATABASE_URL` for Postgres in prod.
* **API base for tools**: `API_BASE` (default `http://127.0.0.1:8000`)

---

## Testing

```bash
pytest -v
# focused tests
pytest -v tests/test_spotcheck.py tests/test_export_csv.py
```

---

## Troubleshooting

* **`'html' is not a package` on startup**
  You have a local `html.py`. Rename it (e.g., `html_utils.py`) and clear caches:

  ```bash
  find . -name "__pycache__" -type d -prune -exec rm -rf {} +
  find . -name "*.pyc" -delete
  ```

* **`ModuleNotFoundError: scrapers` running a script**
  Run from repo root with module mode or set `PYTHONPATH=.`:

  ```bash
  python -m scripts.run_all_scrapers --only-updated
  ```

* **Pushing giant commits / cache files**
  Update `.gitignore`, then:

  ```bash
  git rm -r --cached .
  git add .
  git commit -m "chore: clean repo with updated .gitignore"
  git push origin main
  ```

* **SQLite performance**
  Create helpful indexes and vacuum occasionally:

  ```bash
  sqlite3 dev.db "CREATE INDEX IF NOT EXISTS ix_doc_versions_change_time ON document_versions(change_type, fetched_at DESC);"
  sqlite3 dev.db "VACUUM;"
  ```

---

## Roadmap

* Wave-by-wave state hardening (filters, dedupe, PDF robustness)
* `/ask` RAG endpoint with citations
* Slack/webhook alerting on new changes
* Web dashboard for docs stream, diffs, filters, CSV exports
* NFPA 30 & **IFC** adoption/notice coverage expansion

```

---
