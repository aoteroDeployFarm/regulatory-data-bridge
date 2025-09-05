# Regulatory Data Bridge

End-to-end pipeline for discovering, fetching, and extracting regulatory content (HTML & PDF) across U.S. state sources — ready for RAG and downstream analysis.

* **Generator** converts your config (`state → [urls…]`) into Python scrapers.
* **Scrapers** extract text and track changes (signature + content cache).
* **FastAPI** app exposes admin endpoints to list/run scrapers.
* **CLIs** to batch-run scrapers via Python or directly in-process.

---

## 1) Quick Start

```bash
# 1) Create & activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate         # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# 2) Install deps
python -m pip install -U pip
python -m pip install -r requirements.txt
# (or) minimal set:
# python -m pip install fastapi uvicorn pydantic pydantic-settings httpx requests beautifulsoup4 pypdf pdfminer.six

# 3) Run the API
python -m uvicorn app.main:app --reload

# 4) Open docs
# http://127.0.0.1:8000/docs
```

> Tip: In VS Code, select the interpreter inside `.venv`
> (Cmd/Ctrl+Shift+P → “Python: Select Interpreter”).

---

## 2) Settings & Environment

We keep a simple root-level `settings.py` (Pydantic Settings). It reads `.env` if present.

**.env example (`.env.example`)**

```ini
# App
APP_NAME="Regulatory Data Bridge"
API_VERSION="0.1.0"
ENVIRONMENT="local"
DEBUG=false
LOG_LEVEL="info"

# Server defaults
HOST="127.0.0.1"
PORT=8000

# CORS: comma-separated, or leave "*" for any
CORS_ORIGINS="*"

# Optional integrations
OPENAI_API_KEY=
GOOGLE_API_KEY=
GEMINI_MODEL="models/gemini-1.5-pro"
SLACK_WEBHOOK_URL=
```

**Ignore secrets**

```
# .gitignore (ensure these are present)
.env
.venv/
__pycache__/
```

---

## 3) Project Layout

```
.
├─ app/
│  ├─ main.py                 # FastAPI app (includes routers if present)
│  └─ routers/
│     ├─ admin.py             # List & run scrapers via API
│     ├─ updates.py           # (your project route, optional)
│     └─ ...                  # (ask, process, notifications ...)
├─ scrapers/
│  └─ state/
│     ├─ al/
│     │  ├─ __init__.py
│     │  └─ alabama-gsa-state-al-us-ogb_html_scraper.py
│     ├─ ca/
│     └─ ...                  # one folder per 2-letter state code
├─ scripts/
│  ├─ generate_scrapers_from_json.py   # generator (state → urls)
│  ├─ run_all_scrapers.py              # batch-run scrapers in-process
│  └─ admin_client.py                  # call admin API (list/scrape/bulk)
├─ state-website-data/
│  └─ state-website-data.json          # config (dict: state → [urls...])
├─ settings.py                 # Pydantic settings (root-level)
├─ requirements.txt
├─ requirements-dev.txt
└─ README.md
```

---

## 4) Config → Scrapers (Generator)

Your config is a dict of **`"State Name": [url, ...]`**:

```json
{
  "Alabama": [
    "https://www.gsa.state.al.us/ogb",
    "https://adem.alabama.gov/air"
  ],
  "Alaska": [
    "https://dec.alaska.gov/air/air-permit/",
    "https://rca.alaska.gov/RCAWeb/home.aspx"
  ]
}
```

**Generate scrapers** (state-aware layout + caching + extraction):

```bash
python scripts/generate_scrapers_from_json.py \
  --config ./state-website-data/state-website-data.json \
  --outdir ./scrapers \
  --overwrite
```

* Output files land in `scrapers/state/<state_code>/...`
* HTML files end with `_html_scraper.py`, PDFs with `_pdf_scraper.py`.
* Each scraper maintains a `.cache/` folder (signature + extracted content).

**HTML extraction**

* Uses `BeautifulSoup` to extract text from the page.
* Default selector: `main, article, section, h1, h2, h3` (override at runtime).

**PDF extraction**

* Uses `pypdf` (and/or `pdfminer.six`) to extract text from bytes.

**Unified result schema**

```json
{
  "url": "<source url>",
  "updated": true,
  "diffSummary": "Content/signature changed",
  "new_content": "…",
  "old_content": "…",
  "meta": {
    "content_type": "html|pdf",
    "selector_used": "… or null",
    "signature": "etag=...|lm=...|cl=... or sha256=…",
    "fetched_at": "2025-09-05T18:00:00Z"
  }
}
```

---

## 5) Running Scrapers

### A) Admin API (FastAPI)

Start the API:

```bash
python -m uvicorn app.main:app --reload
# docs at: http://127.0.0.1:8000/docs
```

**List scrapers**

* `GET /admin/scrapers`

  * Optional `?state=tx`

**Run one scraper**

* `POST /admin/scrape?source_id=<filename_stem>`

  * Optional `&state=tx` (if duplicates)
  * Optional `&force=true` (clear `.cache` first)
  * Optional `&selector=main,article` (HTML override)

Examples:

```bash
# List
curl -s http://127.0.0.1:8000/admin/scrapers | jq '.[0:5]'

# Run one
curl -s -X POST \
  "http://127.0.0.1:8000/admin/scrape?source_id=alabama-gsa-state-al-us-ogb_html_scraper" \
  | jq

# Force & override selector
curl -s -X POST \
  "http://127.0.0.1:8000/admin/scrape?source_id=..._html_scraper&force=true&selector=main,article" \
  | jq
```

> If you paste the URL in a browser (GET), you’ll get 405. Use **POST** from Swagger UI or curl.
> (You can allow GET by changing the decorator to `@router.api_route("/scrape", methods=["GET","POST"])`.)

### B) Python Admin Client (HTTP)

`scripts/admin_client.py` (no curl needed):

```bash
# list
python scripts/admin_client.py list
python scripts/admin_client.py list --state tx

# run one
python scripts/admin_client.py scrape \
  --source-id alabama-gsa-state-al-us-ogb_html_scraper

# bulk via API, write JSONL
python scripts/admin_client.py bulk \
  --state ca --pattern air --limit 5 --only-updated \
  --out data/runs/api_bulk.jsonl
```

### C) Batch Runner (In-process)

Run all scrapers locally (no HTTP hop), persist JSONL:

```bash
python scripts/run_all_scrapers.py \
  --workers 8 \
  --out data/runs/scrape_$(date -u +%Y%m%dT%H%M%SZ).jsonl

# filters
python scripts/run_all_scrapers.py --state tx --pattern air --limit 5
python scripts/run_all_scrapers.py --only-updated
```

---

## 6) Caching & Change Detection

Each scraper stores:

* **`last_signature.json`** — last observed signature (ETag/Last-Modified/Content-Length or sha256 of full content).
* **`last_content.txt`** — last extracted text (for `old_content` diffs).

Cache path: `scrapers/state/<code>/<scraper_dir>/.cache/`

Use `force=true` in the admin route to clear cache before running one.

---

## 7) Requirements

**`requirements.txt`**

```txt
fastapi
uvicorn
pydantic
pydantic-settings
httpx
requests
beautifulsoup4
pypdf
pdfminer.six
```

**`requirements-dev.txt`**

```txt
pytest
pytest-asyncio
httpx
requests
beautifulsoup4
pypdf
pdfminer.six
```

Install:

```bash
python -m pip install -r requirements.txt
# (dev)
python -m pip install -r requirements-dev.txt
```

---

## 8) Makefile (optional convenience)

```
.PHONY: api gen run-scrapers

api:
\tpython -m uvicorn app.main:app --reload

gen:
\tpython scripts/generate_scrapers_from_json.py --config ./state-website-data/state-website-data.json --outdir ./scrapers --overwrite

run-scrapers:
\tpython scripts/run_all_scrapers.py --workers 12
```

Usage:

```bash
make api
make gen
make run-scrapers
```

---

## 9) Troubleshooting

**Pylance “Import could not be resolved”**

* Ensure VS Code uses the `.venv` interpreter.
* Install deps (`httpx`, `bs4`, `pypdf`, `pdfminer.six`).
* Reload VS Code window.

**`ModuleNotFoundError: settings`**

* We use root `settings.py`. Make sure `app/main.py` imports:

  ```python
  from settings import Settings, get_settings
  ```
* Ensure `app/__init__.py` and `app/routers/__init__.py` exist if needed.

**405 on `/admin/scrape`**

* Use **POST** (`curl -X POST` or Swagger UI).
* Or change the decorator to accept GET.

**404 `/favicon.ico`**

* Harmless. Add a `static/favicon.ico` if you want to silence it.

**Windows venv activation**

* PowerShell: `.\.venv\Scripts\Activate.ps1`
* If policy error: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

---

## 10) Next Steps (nice to have)

* **/admin/cache/clear** endpoint (per state or all).
* **/admin/scrape-all** endpoint (trigger batch from API).
* **Store results** (SQLite/Postgres) and index `new_content` for RAG.
* **Notifications** (Slack/Webhooks) on impactful updates.
* **Dashboard** (React/HTMX) querying stored updates + RAG answers.

---
