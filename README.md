# Regulatory Data Bridge

Scrape and ingest **public regulatory sources** (HTML & PDF), normalize them, detect changes, and serve them via a FastAPI backend. Designed for downstream **RAG (ChatGPT/Gemini)**, monitoring, and **alerts**.

---

## Table of Contents

- [Regulatory Data Bridge](#regulatory-data-bridge)
  - [Table of Contents](#table-of-contents)
  - [Highlights](#highlights)
  - [Quick Start](#quick-start)
    - [0. Prerequisites](#0-prerequisites)
    - [1. Setup](#1-setup)
    - [2. Run the API (dev)](#2-run-the-api-dev)
    - [3. (Optional) Environment](#3-optional-environment)
  - [Project Layout](#project-layout)
  - [Configuration](#configuration)
  - [Admin API](#admin-api)
    - [Ingest](#ingest)
    - [Sources](#sources)
    - [Cleanup](#cleanup)
  - [Filters](#filters)
  - [Documents API](#documents-api)
  - [Testing](#testing)
  - [Scripts](#scripts)
    - [Run all scrapers](#run-all-scrapers)
    - [Cleanup utility](#cleanup-utility)
  - [NFPA 30 \& IFC Coverage](#nfpa-30--ifc-coverage)
  - [GitHub Issues Import](#github-issues-import)
  - [Makefile](#makefile)
  - [Troubleshooting](#troubleshooting)
  - [Roadmap](#roadmap)

---

## Highlights

* **Generator → hundreds of scrapers** from a single JSON config (`state-website-data/state-website-data.json`)
* **Admin API** for ingestion, cleanup, and source management
* **Filters** that drop noisy/non-doc links (e.g. *Home*, *Contact Us*, `mailto:`, `tel:`, fragments)
* **HTML & PDF support**

  * HTML: BeautifulSoup extraction + JSON-LD fallback
  * PDF: text extraction (`pypdf` / `pdfminer`)
* **Per-scraper caching** (no collisions; safe re-runs)
* **Testing suite** with spot-checks and CSV validation
* **Cleanup tools** to prune non-documents automatically
* **NFPA 30 & IFC coverage plan** (public adoption & notice pages only)

---

## Quick Start

### 0. Prerequisites

* Python **3.11+** (3.12 is fine)
* `jq` (for pretty JSON in shell), optional
* `gh` (GitHub CLI), optional

### 1. Setup

```bash
python3 -m venv .venv
source .venv/bin/activate   # (macOS/Linux)
# .\.venv\Scripts\Activate.ps1   # (Windows PowerShell)

python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
```

### 2. Run the API (dev)

```bash
python3 -m uvicorn app.main:app --reload
# visit http://127.0.0.1:8000/docs
```

### 3. (Optional) Environment

`.env` file:

```ini
APP_ENV=dev
APP_HOST=127.0.0.1
APP_PORT=8000
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173
HTTP_TIMEOUT_SECONDS=30
DEFAULT_USER_AGENT=regulatory-data-bridge/1.0 (+https://example.com)
```

---

## Project Layout

```
regulatory-data-bridge/
├─ app/
│  ├─ main.py                 # FastAPI bootstrap
│  ├─ routers/
│  │  ├─ admin.py             # ingest, cleanup, toggle, upsert
│  │  ├─ documents.py         # search + export.csv
│  │  └─ sources.py           # source listing
│  ├─ scrapers/
│  │  ├─ html.py              # HTML ingestion
│  │  ├─ rss.py               # RSS ingestion
│  │  └─ http.py              # session helpers
│  ├─ lib/
│  │  └─ filters.py           # URL/title filtering rules
│  ├─ db/                     # models, session, crud
│  └─ services/
│     └─ ingest.py            # ingestion orchestrator
├─ scripts/
│  ├─ admin_client.py
│  ├─ run_all_scrapers.py
│  ├─ generate_scrapers_from_json.py
│  └─ full_cleanup.py
├─ state-website-data/
│  └─ state-website-data.json
├─ tests/
│  ├─ test_spotcheck.py       # doc validity
│  └─ test_export_csv.py      # CSV export validity
├─ settings.py
├─ requirements.txt
└─ README.md
```

---

## Configuration

Sources live in `state-website-data/state-website-data.json`.

```json
{
  "Texas": [
    "https://www.tdi.texas.gov/fire/fmfsinotices.html",
    "https://www.tceq.texas.gov/downloads/rules/adoptions/22015338_ado.pdf"
  ],
  "California": [
    "https://osfm.fire.ca.gov/what-we-do/code-development-and-analysis"
  ],
  "Florida": [
    "https://myfloridacfo.com/division/sfm/bfp/florida-fire-prevention-code"
  ]
}
```

Regenerate scrapers:

```bash
python3 scripts/generate_scrapers_from_json.py \
  --config ./state-website-data/state-website-data.json \
  --outdir ./scrapers --overwrite
```

---

## Admin API

### Ingest

```bash
curl -s -X POST http://127.0.0.1:8000/admin/ingest | jq
```

### Sources

```bash
# toggle
curl -s -X POST "http://127.0.0.1:8000/admin/sources/toggle?name=Texas%20RRC%20–%20News&active=false" | jq

# upsert
curl -s -X POST http://127.0.0.1:8000/admin/sources/upsert \
  -H "Content-Type: application/json" \
  -d '{"name":"Example","url":"https://example.com/news","jurisdiction":"EX","type":"html","active":true}'
```

### Cleanup

```bash
# Drop bad schemes/links
curl -s -X POST http://127.0.0.1:8000/admin/cleanup/fragment-only | jq
curl -s -X POST http://127.0.0.1:8000/admin/cleanup/trailing-hash | jq
curl -s -X POST http://127.0.0.1:8000/admin/cleanup/non-http | jq

# Drop nav titles
curl -s -X POST "http://127.0.0.1:8000/admin/cleanup/titles-exact?title=Home" | jq
curl -s -X POST "http://127.0.0.1:8000/admin/cleanup/titles-exact?title=Skip%20To%20Main%20Content" | jq
```

---

## Filters

Defined in `app/lib/filters.py`.

* Block: `mailto:`, `tel:`, `javascript:`, `#`
* Block paths: `/about`, `/contact`, `/forms`, `/resources`, `/site-policies`
* Block titles: *Home*, *About Us*, *Announcements*
* Allow: `/news`, `/press`, `/updates`, `/rulemaking`, `/notices`, `/library`
* Require either doc-like path hints or deep path structure

---

## Documents API

Search:

```bash
curl -s "http://127.0.0.1:8000/documents?limit=10" | jq
```

Export CSV:

```bash
curl -s "http://127.0.0.1:8000/documents/export.csv?jurisdiction=TX&limit=200" -o out.csv
```

---

## Testing

```bash
pytest -v tests/test_spotcheck.py tests/test_export_csv.py
```

* **Spotcheck**: verifies valid docs exist per jurisdiction
* **CSV**: validates headers, row quality, URL/title checks

Failures often indicate stray nav links (*Home*, `mailto:`, `#`, etc.).

---

## Scripts

### Run all scrapers

```bash
python3 scripts/run_all_scrapers.py --only-updated
```

### Cleanup utility

```bash
python3 scripts/full_cleanup.py --base-url http://127.0.0.1:8000
```

---

## NFPA 30 & IFC Coverage

* **Seeded**: TX, CA, FL
* **Wave A**: OK, LA, NM, CO, ND, PA, OH, WY, WV, UT, AZ
* Add 10–12 states per wave

Focus:

* Fire Marshal adoption pages
* Admin Code adoptions
* Registers & notices

---

## GitHub Issues Import

```bash
export GITHUB_TOKEN=ghp_xxx
python3 scripts/import_issues.py --file issues_nfpa_ifc.json --repo OWNER/REPO
```

---

## Makefile

```makefile
install:
	python3 -m pip install -r requirements.txt
api:
	python3 -m uvicorn app.main:app --reload
gen:
	python3 scripts/generate_scrapers_from_json.py --config ./state-website-data/state-website-data.json --outdir ./scrapers --overwrite
run-scrapers:
	python3 scripts/run_all_scrapers.py --only-updated
```

---

## Troubleshooting

* **SQLite `ILIKE` error** → replaced with `LIKE`
* **Bad links (mailto, tel, #)** → run cleanup endpoints
* **Empty PDFs** → install `pdfminer.six`
* **Reload loops** → check router syntax

---

## Roadmap

* Finish Wave A ingestion & cleanup
* Expand filter rules for noisy sites
* Add `/ask` RAG endpoint with citations
* Slack/webhook alerts
* Web dashboard + mobile app

---

✅ This is now a **comprehensive README with TOC**.

Want me to also generate a **badge block at the very top** (Python version, pytest, license, etc.) so it looks more professional for GitHub?
