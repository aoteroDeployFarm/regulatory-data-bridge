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
    - [Handy scripts (when present)](#handy-scripts-when-present)
    - [Make (add these to your `Makefile` if desired)](#make-add-these-to-your-makefile-if-desired)
  - [Configuration](#configuration)
  - [Testing](#testing)
  - [Troubleshooting](#troubleshooting)
  - [Roadmap](#roadmap)

---

## Highlights

* **Hundreds of scrapers** (federal + all 50 states) generated/organized under `scrapers/…`
* **Admin API**: ingest, cleanup, toggle/activate sources, bulk ops
* **Filters** to drop nav/noise links (`mailto`, `tel`, fragments, “Home”, etc.)
* **HTML & PDF** pipelines (BeautifulSoup + PDF extraction)
* **Per-source caching** and optional `force` refresh
* **CSV export** for downstream analytics and BI tools

---

## Repo Layout

```
regulatory-data-bridge/
  app/                 # FastAPI app (main.py, routers, services, db)
  scrapers/            # Generated scrapers (federal/ + state/<abbr>/...)
  docs/                # API notes & curl examples
  openapi/             # OpenAPI specs (federal/state/internal)
  requirements.txt
  Makefile.mak
  dev.db               # Default SQLite dev database
```

> The API entrypoint is `app/main.py`. Seed helpers live under `app/seeds/`. Routers for `/admin`, `/documents`, etc. are in `app/routers/`.&#x20;

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
```

### 2) Fix stdlib name-clash (one-time)

If a top-level `html.py` exists, rename it (it shadows Python’s `html` stdlib and breaks FastAPI/Starlette):

```bash
mv html.py html_utils.py
find . -name "__pycache__" -type d -prune -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### 3) Seed sources

Register all sources (federal + states) into the DB:

```bash
export PYTHONPATH=.
python app/seeds/seed_sources.py
```

### 4) Run the API

```bash
uvicorn app.main:app --reload --port 8000
# http://127.0.0.1:8000/docs
```

---

## Activate & Run All 50 States

### A) Activate all sources

**Option 1 — bulk toggle (if endpoint exists):**

```bash
curl -s -X POST "http://127.0.0.1:8000/admin/sources/activate-all" | jq
```

**Option 2 — one-liner via Python (always works):**

```bash
PYTHONPATH=. python - <<'PY'
from app.db.session import get_engine, get_session
from app.db.models import Source
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

**Target specific states/patterns (if supported in your build):**

```bash
curl -s "http://127.0.0.1:8000/admin/scrape-all?state=tx,ca,co&pattern=fire&limit=5&force=true" | jq
```

> Admin/ingest & sources routers are under `app/routers/`. Services live under `app/services/ingest.py`.&#x20;

---

## Admin API

* **Ingest all active sources**
  `POST /admin/ingest` → `{ ok, count, updated, failed, ... }`

* **Toggle a source**
  `POST /admin/sources/toggle?name=...&active=true|false`

* **(Optional) Bulk activate**
  `POST /admin/sources/activate-all`

* **Cleanup helpers** (drop noisy links/titles):

  * `POST /admin/cleanup/fragment-only`
  * `POST /admin/cleanup/trailing-hash`
  * `POST /admin/cleanup/non-http`
  * `POST /admin/cleanup/titles-exact?title=Home`

> See `docs/curl-scrapers.md` for concrete command examples.&#x20;

---

## Documents API

* **Search**
  `GET /documents?limit=20&jurisdiction=TX`

* **Export CSV**
  `GET /documents/export.csv?jurisdiction=CO&limit=500`

Routers: `app/routers/documents.py`.&#x20;

---

## Scripts & Make Targets

### Handy scripts (when present)

Run scripts as modules so imports resolve from repo root:

```bash
python -m scripts.run_all_scrapers --only-updated
python -m scripts.run_all_scrapers --state "TX,CA" --pattern fire --limit 5
```

If you run scripts directly, set `PYTHONPATH=.`.

### Make (add these to your `Makefile` if desired)

```makefile
install:
\tpip install -r requirements.txt

api:
\tuvicorn app.main:app --reload --port 8000

seed:
\tPYTHONPATH=. python app/seeds/seed_sources.py

activate-all:
\tPYTHONPATH=. python - <<'PY'\nfrom app.db.session import get_engine, get_session\nfrom app.db.models import Source\nengine = get_engine()\nwith get_session(engine) as db:\n    n = db.query(Source).update({Source.active: True})\n    db.commit()\n    print(f"Activated {n} sources.")\nPY

ingest:
\tcurl -s -X POST "http://127.0.0.1:8000/admin/ingest" | jq
```

> There’s a `Makefile.mak` in the repo you can reference/merge.&#x20;

---

## Configuration

* **Settings**: `app/core/settings.py` (envs, timeouts, CORS, etc.)
* **Database**: `app/db/` (models, session, CRUD; default dev uses `dev.db`)
* **Scraper base**: `scrapers/_base.py`, plus domain/state subpackages
* **OpenAPI**: `openapi/` for internal + federal/state specs



---

## Testing

```bash
pytest -v
# or run focused tests (spotcheck, export csv)
pytest -v tests/test_spotcheck.py tests/test_export_csv.py
```

Common failure hints:

* “No valid docs” → run cleanup endpoints; check filters
* PDF text missing → ensure `pdfminer.six` is installed

---

## Troubleshooting

* **`ModuleNotFoundError: scrapers` when running a script**
  Run from repo root with module mode: `python -m scripts.run_all_scrapers …`
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
