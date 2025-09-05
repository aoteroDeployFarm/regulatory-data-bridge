# Regulatory Data Bridge

> Scrape regulatory sources (HTML & PDF), detect changes, extract content, and power Q\&A + alerts with Gemini/GPT.

[![FastAPI](https://img.shields.io/badge/FastAPI-ready-009688.svg)]()
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)]()

## Table of Contents

- [Regulatory Data Bridge](#regulatory-data-bridge)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Project Structure](#project-structure)
  - [Quick Start](#quick-start)
    - [Requirements](#requirements)
    - [Setup](#setup)
    - [Environment](#environment)
  - [Running the API](#running-the-api)
  - [HTTP Endpoints](#http-endpoints)
  - [Scraper Generation](#scraper-generation)
  - [AI Processing \& RAG](#ai-processing--rag)
  - [Notifications](#notifications)
  - [GitHub Issues Import (Python)](#github-issues-import-python)
  - [Testing](#testing)
  - [Deployment](#deployment)
  - [Roadmap](#roadmap)
  - [License](#license)
    - [Housekeeping](#housekeeping)

---

## Overview

Regulatory Data Bridge monitors agency sources, detects updates, extracts content (HTML & PDF), and makes it queryable via a FastAPI endpoint with retrieval-augmented generation (RAG). It supports both **Gemini** and **OpenAI** providers, shared schema across scrapers, and alerting (Slack & push).

## Features

* ✅ Unified scraper output schema (`url`, `updated`, `new_content`, `old_content`, `meta`)
* ✅ HTML & PDF templates with caching and content extraction
* ✅ FastAPI service with `/ask`, `/updates`, `/process/{id}`, `/notifications/push/register`
* ✅ Typed configuration via **Pydantic v2** (`settings.py`) + `.env` support
* ✅ GitHub issues bulk import with a **Python** script (no bash/gh required)
* 🧠 AI post-processing hooks (summaries, entities, doc class, risk score)
* 🔎 RAG-ready: chunking + embeddings (pgvector friendly)
* 🔔 Slack & push notifications (Expo/FCM/APNs adapters planned)

## Architecture

```
Scrapers (HTML/PDF)  -->  Updates Store  -->  AI Post-Processing  -->  RAG Index
        |                         |                |                     |
        +-- signature/content ----+                +-- summaries/entities+
                                                             |
                                                        FastAPI /ask
```

## Project Structure

```
.
├── app/
│   ├── main.py                      # FastAPI app, CORS, health, routers
│   └── routers/
│       ├── ask.py                   # POST /ask
│       ├── updates.py               # GET /updates
│       ├── process.py               # POST /process/{update_id}
│       └── notifications.py         # POST /notifications/push/register
├── scripts/
│   ├── import_issues.py             # Python GitHub bulk issue importer
│   └── generate_scrapers_from_json.py  # Scraper generator (HTML/PDF)
├── scrapers/                        # Generated scrapers live here
├── data/
│   └── issues.json                  # Issues payload for importer script
├── settings.py                      # Pydantic v2 typed config
├── .env.example                     # Sample environment config
├── README.md
└── .gitignore
```

## Quick Start

### Requirements

* Python **3.11+**
* (Optional) Postgres + pgvector, Redis

### Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip

# API dependencies
pip install fastapi uvicorn pydantic pydantic-settings requests

# Scraper deps
pip install beautifulsoup4 pypdf pdfminer.six

# (Optional) DB/Vector/Workers later:
# pip install "psycopg[binary]" sqlalchemy pgvector tenacity celery redis
```

### Environment

```bash
cp .env.example .env
# Edit .env – set LLM_PROVIDER + matching API key, DB URLs, etc.
```

## Running the API

```bash
uvicorn app.main:app --reload
# Docs: http://localhost:8000/docs
# Health: http://localhost:8000/health
```

## HTTP Endpoints

* `GET /health` – basic status and configuration echo.

* `POST /ask` – **(stub)** Q\&A with citations.
  Request:

  ```json
  { "q": "What changed for air permits in CO?", "top_k": 6, "filters": { "jurisdiction": "CO" } }
  ```

  Response (example placeholder):

  ```json
  {
    "answer": "This is a placeholder answer. RAG pipeline not wired yet.",
    "citations": [{ "url": "https://example.gov/reg/123", "excerpt": "…", "score": 0.82 }],
    "used_filters": { "jurisdiction": "CO" }
  }
  ```

* `GET /updates?jurisdiction=CO&class=Permitting&since=2025-08-01&risk_min=30&limit=50` – **(stub)** list recent updates with filters.

* `POST /process/{update_id}` – **(stub)** trigger AI summarization/entity extraction/classification for an update.

* `POST /notifications/push/register` – **(stub)** register device token for push notifications.

## Scraper Generation

Generate scraper files from JSON config:

```json
// scrapers.json (examples)
[
  {
    "name": "ca_cec",
    "target_url": "https://example.com/cec.html",
    "type": "html",
    "selector": "main, article, section, h1, h2, h3"
  },
  {
    "name": "epa_bulletin",
    "target_url": "https://example.com/bulletin.pdf",
    "type": "pdf"
  }
]
```

Run the generator:

```bash
python scripts/generate_scrapers_from_json.py --config scrapers.json --outdir ./scrapers --overwrite
```

All generated scrapers expose:

```python
result = check_for_update(selector: str | None = None) -> dict
# Unified schema:
# {
#   "url": "...",
#   "updated": true|false,
#   "diffSummary": "...",
#   "new_content": "text or null",
#   "old_content": "text or empty",
#   "meta": {
#     "content_type": "html|pdf",
#     "selector_used": "..." or null,
#     "signature": "etag|lm|cl or sha256",
#     "fetched_at": "ISO-8601"
#   }
# }
```

## AI Processing & RAG

* **Providers:** choose with `LLM_PROVIDER=gemini|openai` and set the matching API key.
* **Planned outputs per update:** `summary.short`, `summary.detailed`, `bullet_changes`, `entities[]`, `doc_class`, `risk_score`.
* **RAG:** chunk `new_content` (size/overlap in `.env`), embed with selected provider/model, store in pgvector for retrieval in `/ask`.

> Until wired, the API returns placeholder responses so frontends can be built in parallel.

## Notifications

* **Slack:** set `SLACK_WEBHOOK_URL` or bot token + `ALERT_CHANNEL`.
* **Push:** choose `PUSH_PROVIDER=expo|fcm|apns` and fill provider creds.
* **Flow:** scrape → (updated) → process AI → evaluate risk/filters → send Slack/push.

## GitHub Issues Import (Python)

Bulk-create issues, labels, and milestones from `data/issues.json`.

**Prep:**

```bash
pip install requests
export GITHUB_TOKEN=ghp_your_token_with_repo_scope
```

**Run:**

```bash
python scripts/import_issues.py --file data/issues.json
# or explicitly target a repo:
python scripts/import_issues.py --file data/issues.json --repo owner/name
# dry run:
python scripts/import_issues.py --file data/issues.json --dry-run
```

`data/issues.json` structure:

```json
{
  "issues": [
    { "title": "Backend: Add /ask endpoint for RAG Q&A",
      "body": "Implement POST /ask...",
      "labels": ["backend","RAG","P0"],
      "milestone": "Phase 1: Core Backend & AI"
    }
  ]
}
```

## Testing

* **API:** `pytest` using FastAPI `TestClient` and snapshot tests for `/ask`, `/updates`.
* **Scrapers:** golden fixtures for HTML/PDF; assert unified schema.
* **AI:** mock client returning deterministic JSON for summaries/entities.

(Testing scaffolds are intentionally light so you can grow them with your storage choices.)

## Deployment

* **Dev:** `uvicorn app.main:app --reload`
* **Prod (example):**

  ```bash
  pip install "uvicorn[standard]" gunicorn
  exec gunicorn -k uvicorn.workers.UvicornWorker -w 4 app.main:app
  ```
* **Env:** copy `.env.example` → `.env` and supply secrets via your platform (Docker/K8s/Render/Fly).

## Roadmap

* Wire AI post-processing (summaries, entities, classification)
* RAG indexer + embeddings (pgvector)
* Real data store for updates/chunks + migrations
* Slack + push adapters with filters & schedules
* Web dashboard (Next.js) and mobile app (Expo)

## License

MIT (see `LICENSE`).

---

### Housekeeping

* Keep secrets out of git: `.env` is ignored; commit only `.env.example`.
* If you change environment or endpoint shapes, reflect them in this README and your frontends’ generated API clients.

---
