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
  - [Scripts \& Make Targets](#scripts--make-targets)
    - [Handy scripts](#handy-scripts)
    - [Make (optional)](#make-optional)
  - [Configuration](#configuration)
  - [Testing](#testing)
  - [Troubleshooting](#troubleshooting)
  - [Roadmap](#roadmap)
  - [Quick API ops (curl)](#quick-api-ops-curl)
    - [Seed / activate sources from JSON](#seed--activate-sources-from-json)
    - [Ingest (run all active scrapers once)](#ingest-run-all-active-scrapers-once)
    - [Cleanup (drop noise)](#cleanup-drop-noise)
    - [Source management](#source-management)
    - [Documents API](#documents-api-1)
    - [Dev UI](#dev-ui)
  - [Scheduled runs (cron)](#scheduled-runs-cron)
    - [1) Create the helper script](#1-create-the-helper-script)
    - [2) Add cron entries](#2-add-cron-entries)

---

## Highlights

* **Hundreds of scrapers** (federal + all 50 states) organized in `scrapers/…`
* **Admin API**: ingest, cleanup, toggle/activate sources, bulk ops
* **Filters** to drop nav/noise links (`mailto`, `tel`, fragments, “Home”, etc.)
* **HTML & PDF** pipelines (BeautifulSoup + PDF extraction)
* **Per-source caching** and optional `force` refresh
* **CSV export** for downstream analytics and BI tools

---

## Repo Layout

```text
regulatory-data-bridge/
  app/                 # FastAPI app (main.py, routers, services, db)
  scrapers/            # Generated scrapers (federal/ + state/<abbr>/...)
  state-website-data/  # JSON sources (single source of truth)
  tools/               # helper scripts (upsert/activate/etc.)
  tests/
  requirements.txt
  Makefile             # optional
  dev.db               # default SQLite dev database (ignored in prod)
````

> API entrypoint: `app/main.py`. Routers under `app/routers/` (`/admin`, `/documents`, …).

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
python3 -m pip install -U pip
pip install -r requirements.txt
```

### 2) Fix stdlib name-clash (one-time)

If a top-level `html.py` exists, rename it (it shadows Python’s `html` stdlib and breaks FastAPI/Starlette):

```bash
mv html.py html_utils.py
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### 3) Seed sources

Register all state/federal sources from JSON into the DB:

```bash
python3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json --commit-per-state
```

### 4) Run the API

```bash
uvicorn app.main:app --reload --port 8000
# http://127.0.0.1:8000/docs
```

---

## Activate & Run All 50 States

### A) Activate all sources

**Option 1 — bulk toggle endpoint (if available in your build):**

```bash
curl -s -X POST "http://127.0.0.1:8000/admin/sources/activate-all" | jq
```

**Option 2 — helper script:**

```bash
python3 tools/activate_sources.py --seed
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
  `GET /documents?limit=20&jurisdiction=TX`

* **Export CSV**
  `GET /documents/export.csv?jurisdiction=CO&limit=500`

---

## Scripts & Make Targets

### Handy scripts

Run scripts as **modules** so imports resolve from repo root:

```bash
python3 -m scripts.run_all_scrapers --only-updated
python3 -m scripts.run_all_scrapers --state "TX,CA" --pattern fire --limit 5
```

### Make (optional)

> Note: Make requires **TAB** characters before command lines.

```makefile
install:
	python3 -m pip install -r requirements.txt

api:
	uvicorn app.main:app --reload --port 8000

seed:
	python3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json --commit-per-state

activate-all:
	python3 tools/activate_sources.py --seed

ingest:
	curl -s -X POST "http://127.0.0.1:8000/admin/ingest" | jq
```

---

## Configuration

* **Settings**: `app/core/settings.py` (envs, timeouts, CORS, etc.)
* **Database**: `app/db/` (models, session, CRUD; default dev uses `dev.db`)
* **Source list**: `state-website-data/state-website-data.json` (single source of truth)

---

## Testing

```bash
pytest -v
# or run focused tests
pytest -v tests/test_spotcheck.py tests/test_export_csv.py
```

---

## Troubleshooting

* **`ModuleNotFoundError: scrapers` when running a script**
  Run from repo root with module mode: `python3 -m scripts.run_all_scrapers …`
  or set `PYTHONPATH=.`. Add `__init__.py` to packages if missing.

* **`'html' is not a package` on startup**
  You have a local `html.py` shadowing the stdlib. Rename it (e.g., `html_utils.py`) and clear `__pycache__`.

* **Hot-reload loops**
  Syntax errors in a router or service; check `app/routers/*` and `app/services/ingest.py`.

* **Push errors / giant commits**
  Update `.gitignore`, then:

  ```bash
  git rm -r --cached .
  git add .
  git commit -m "chore: clean repo with updated .gitignore"
  git push origin main
  ```

* **Speed tips**
  Use `--only-updated` in scripts, or default cached ingest; reserve `force=true` for spot re-runs.

---

## Roadmap

* Wave-by-wave state hardening (filters, dedupe, PDF robustness)
* `/ask` RAG endpoint with citations
* Slack/webhook alerting on new changes
* Web dashboard (docs stream, diffs, filters, CSV exports)
* NFPA 30 & **IFC** adoption/notice coverage expansion

---

## Quick API ops (curl)

Tip: install `jq` for pretty JSON.
Optional: set a base URL:

```bash
export BASE=http://127.0.0.1:8000
```

### Seed / activate sources from JSON

```bash
python3 tools/upsert_state_sites.py --file ./state-website-data/state-website-data.json --commit-per-state
```

### Ingest (run all active scrapers once)

```bash
curl -s -X POST ${BASE:-http://127.0.0.1:8000}/admin/ingest | jq .
```

### Cleanup (drop noise)

```bash
# Bad fragments / trailing hashes / non-http schemes
curl -s -X POST ${BASE:-http://127.0.0.1:8000}/admin/cleanup/fragment-only | jq .
curl -s -X POST ${BASE:-http://127.0.0.1:8000}/admin/cleanup/trailing-hash | jq .
curl -s -X POST ${BASE:-http://127.0.0.1:8000}/admin/cleanup/non-http | jq .

# Common nav titles
curl -s -X POST "${BASE:-http://127.0.0.1:8000}/admin/cleanup/titles-exact?title=Home" | jq .
curl -s -X POST "${BASE:-http://127.0.0.1:8000}/admin/cleanup/titles-exact?title=Announcements" | jq .
curl -s -X POST "${BASE:-http://127.0.0.1:8000}/admin/cleanup/titles-exact?title=About%20Us" | jq .
```

### Source management

```bash
# Toggle a single source (name must be URL-encoded)
curl -s -X POST "${BASE:-http://127.0.0.1:8000}/admin/sources/toggle?name=CA%20%E2%80%93%20osfm.fire.ca.gov%2Fwhat-we-do%2Fcode-development-and-analysis&active=false" | jq .

# Upsert a single source manually
curl -s -X POST ${BASE:-http://127.0.0.1:8000}/admin/sources/upsert \
  -H "Content-Type: application/json" \
  -d '{"name":"Example","url":"https://example.com/news","jurisdiction":"EX","type":"html","active":true}' | jq .
```

---

### Documents API

```bash
# Browse a few docs
curl -s "${BASE:-http://127.0.0.1:8000}/documents?limit=10" | jq .

# Export CSV (downloaded to current directory)
curl -s "${BASE:-http://127.0.0.1:8000}/documents/export.csv?jurisdiction=TX&limit=500" -o out_TX.csv
```

### Dev UI

* Swagger UI: `http://127.0.0.1:8000/docs`

---

## Scheduled runs (cron)

You can keep the dataset fresh automatically with a tiny shell helper and two cron entries.

### 1) Create the helper script

```bash
# tools/ingest_cron.sh
#!/usr/bin/env bash
set -euo pipefail

# Base URL of the API (override in cron with BASE=...)
BASE="\${BASE:-http://127.0.0.1:8000}"

echo "[\$(date -Is)] ingest start"
# Run cached ingest (fast re-runs)
curl -fsS -X POST "\$BASE/admin/ingest" | jq -r . || echo "ingest failed"

# Optional light cleanup passes (best-effort)
curl -fsS -X POST "\$BASE/admin/cleanup/fragment-only"    >/dev/null || true
curl -fsS -X POST "\$BASE/admin/cleanup/trailing-hash"    >/dev/null || true
curl -fsS -X POST "\$BASE/admin/cleanup/non-http"         >/dev/null || true

echo "[\$(date -Is)] ingest done"
````

Make it executable and create a logs folder:

```bash
chmod +x tools/ingest_cron.sh
mkdir -p logs
```

### 2) Add cron entries

Open your crontab:

```bash
crontab -e
```

Paste these lines (adjust absolute paths as needed):

```cron
# Daily cached ingest at 02:15
15 2 * * * /bin/bash -lc '/full/path/tools/ingest_cron.sh >> /full/path/logs/ingest.log 2>&1'

# Weekly forced refresh Sunday at 03:05 (bypasses cache)
5 3 * * 0  /bin/bash -lc 'BASE=http://127.0.0.1:8000 curl -fsS -X POST "$BASE/admin/ingest?force=true" >> /full/path/logs/ingest.log 2>&1 || true'
```

> **Notes**
>
> * Ensure the API is running (e.g., `uvicorn app.main:app --reload --port 8000`) when cron fires.
> * You can tail logs with: `tail -f logs/ingest.log`.
> * For production, consider Postgres and a process manager (systemd, Docker, Kubernetes) and a system scheduler (systemd timers).
