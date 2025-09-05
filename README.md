# Regulatory Data Bridge

Scrape public regulatory sources (HTML & PDF), detect changes, capture diffs/content, and serve them via a FastAPI backend. Designed for downstream RAG (ChatGPT/Gemini) and notifications.

## Highlights

* **Generator → hundreds of scrapers** from a single JSON config (`state-website-data/state-website-data.json`)
* **HTML & PDF support**

  * HTML: BeautifulSoup extraction with customizable selectors
  * PDF: automatic text extraction (pypdf/pdfminer) with content caching
* **Per-scraper caching** (no collisions; fast re-runs)
* **Admin API** for listing/running scrapers, batch runs, and cache cleaning
* **CLI helpers** (`scripts/admin_client.py`, `scripts/run_all_scrapers.py`)
* **Issues import** workflow for tracking work in GitHub (compatible with REST API importer)
* **NFPA 30 & IFC** workflow (public sources only; no paywalled code text)

---

## Quick start

### 0) Prerequisites

* Python **3.11+** recommended (3.12 fine)
* `jq` (for pretty JSON in shell), optional
* `gh` (GitHub CLI) for repo checks, optional

### 1) Setup a virtualenv and install

```bash
python3 -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1

python3 -m pip install -U pip
python3 -m pip install -r requirements.txt
```

### 2) (Optional) Environment file

You can keep sensitive settings in a `.env` file (not committed). Example:

```
# .env (example)
APP_ENV=dev
APP_HOST=127.0.0.1
APP_PORT=8000

# CORS
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5173,http://localhost:5173

# Timeouts & HTTP
HTTP_TIMEOUT_SECONDS=30
DEFAULT_USER_AGENT=regulatory-data-bridge/1.0 (+https://example.com)

# Integrations (optional)
SLACK_WEBHOOK_URL=
OPENAI_API_KEY=
GEMINI_API_KEY=
```

> The app reads from `settings.py` (Pydantic) which also supports environment variables.

### 3) Run the API (dev)

```bash
python3 -m uvicorn app.main:app --reload
# visit http://127.0.0.1:8000 and /docs
```

---

## Project layout (key pieces)

```
regulatory-data-bridge/
├─ app/
│  ├─ main.py                # FastAPI app bootstrap
│  └─ routers/
│     ├─ updates.py          # (optional) business routes
│     └─ admin.py            # admin endpoints (list/scrape/batch/cache)
├─ scrapers/                 # generated scrapers live here
│  └─ state/<code>/
│     ├─ <stem>_html_scraper.py
│     ├─ <stem>_pdf_scraper.py
│     └─ .cache/<stem>/      # per-scraper cache (signature/content)
├─ state-website-data/
│  └─ state-website-data.json # input config: state -> [urls...]
├─ scripts/
│  ├─ generate_scrapers_from_json.py
│  ├─ run_all_scrapers.py
│  ├─ admin_client.py
│  └─ import_issues.py        # working REST API importer
├─ settings.py                # configuration (Pydantic)
├─ README.md
└─ requirements.txt
```

---

## Configuration: add sources

The generator uses `state-website-data/state-website-data.json`:

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

> Keep these **public** (adoption pages, notices, rule text). Do not include paywalled code text.

---

## Generate scrapers

```bash
python3 scripts/generate_scrapers_from_json.py \
  --config ./state-website-data/state-website-data.json \
  --outdir ./scrapers \
  --overwrite
```

* Files land under `scrapers/state/<state_code>/...`
* Filenames are sanitized from the URL and suffixed with `_html_scraper.py` or `_pdf_scraper.py`
* **Per-scraper cache** is created at:
  `scrapers/state/<state_code>/.cache/<scraper_stem>/`
  containing:

  * `last_signature.json`
  * `last_content.txt` (extracted text)

---

## Admin API (new)

* List scrapers
  `GET /admin/scrapers?state=tx&pattern=fire`

* Run **one** scraper
  `POST /admin/scrape?source_id=<stem>&state=tx&force=true`

* **Batch** run many scrapers
  `GET|POST /admin/scrape-all?state=tx&pattern=fire&limit=5&force=true&only_updated=true`

* **Clear caches** without running
  `GET|POST /admin/cache/clear?state=tx&pattern=fire&include_legacy=false`

Examples:

```bash
# list
curl -s "http://127.0.0.1:8000/admin/scrapers?state=tx&pattern=fire" | jq

# run one
curl -s -X POST \
  "http://127.0.0.1:8000/admin/scrape?source_id=texas-tdi-texas-gov-fire-fmfsinotices-html_html_scraper&state=tx&force=true" \
  | jq

# batch
curl -s "http://127.0.0.1:8000/admin/scrape-all?state=tx&pattern=nfpa&limit=3&force=true&only_updated=true" | jq

# clear caches
curl -s -X POST "http://127.0.0.1:8000/admin/cache/clear?state=tx&pattern=fire" | jq
```

> `force=true` recreates the per-scraper cache directory to avoid ENOENT.

---

## CLI helpers

### List / run from the client script

```bash
# list (filter by state)
python3 scripts/admin_client.py list --state tx | jq

# run one (force a fresh fetch)
python3 scripts/admin_client.py scrape \
  --source-id texas-..._html_scraper --force | jq

# bulk run
python3 scripts/admin_client.py bulk \
  --state tx --pattern fire --limit 5 --force --only-updated
```

### In-process runner

```bash
python3 scripts/run_all_scrapers.py --only-updated
# add --workers N for concurrency (IO-bound, keep it modest)
```

---

## HTML selectors & PDF extraction

* **HTML** scrapers default to a general selector (e.g., `main, article, h1, h2, h3, a`).
  You can override at runtime:

  ```bash
  python3 scripts/admin_client.py scrape \
    --source-id texas-..._html_scraper \
    --selector "main,article,.content,.notice" \
    --force | jq
  ```
* **PDF** scrapers try `pypdf` first, then `pdfminer.six` if available.
  Add one of these to `requirements.txt`:

  ```
  pypdf>=4
  # or
  pdfminer.six>=202312
  ```

Both HTML and PDF scrapers return:

```json
{
  "url": "...",
  "updated": true,
  "diffSummary": "PDF signature changed" | "No change" | "...",
  "new_content": "...",
  "old_content": "...",
  "meta": { "content_type": "html|pdf", "..."}
}
```

---

## NFPA 30 & IFC coverage (plan)

We’re tracking **public** sources (adoption pages, state admin rules adopting by reference, notices/errata). No scraping paywalled code text.

### Waves

* **Seeded**: TX, CA, FL
* **Wave A** (created issues): OK, LA, NM, CO, ND, PA, OH, WY, WV, UT, AZ
* Next waves add remaining states in batches of \~10–12.

### Sourcing tips

* Fire Marshal / Fire Prevention adoption/notice pages
* State Admin Code/Rules adopting **NFPA 30** by reference
* State Register / rulemaking notices
* (Optional) one large city’s adoption page (local amendments)

Use searches like:

```
site:.gov "<STATE>" "State Fire Marshal" "fire code" adoption
site:.gov "<STATE>" "International Fire Code" adoption
site:.gov "<STATE>" "NFPA 30" "incorporated by reference"
site:.gov "<STATE>" register "fire code"
```

Add 2–5 URLs per state to `state-website-data.json`, regenerate scrapers, and spot-run.

---

## Importing tracking issues to GitHub

We use the **working** REST API importer: `scripts/import_issues.py`.

### Token & repo

```bash
export GITHUB_TOKEN=ghp_XXXXXXXXXXXXXXXXXXXX
# enable Issues if needed:
# gh repo edit OWNER/REPO --enable-issues
```

### Import the NFPA/IFC base set

```bash
python3 scripts/import_issues.py \
  --file issues_nfpa_ifc.json \
  --repo OWNER/REPO
```

### Import Wave A issues

```bash
python3 scripts/import_issues.py \
  --file issues_fire_codes_wave_a.json \
  --repo OWNER/REPO
```

### Verify

```bash
gh issue list --repo OWNER/REPO \
  --label "batch:fire-codes-phase1" --limit 200 --json number,title,url

gh issue list --repo OWNER/REPO \
  --label "batch:fire-codes-waveA" --limit 200 --json number,title,url
```

---

## Makefile (optional QoL)

```makefile
PY ?= python3
PIP ?= $(PY) -m pip

.PHONY: install api gen run-scrapers list scrape

install:
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt

api:
	$(PY) -m uvicorn app.main:app --reload

gen:
	$(PY) scripts/generate_scrapers_from_json.py \
	  --config ./state-website-data/state-website-data.json \
	  --outdir ./scrapers --overwrite

run-scrapers:
	$(PY) scripts/run_all_scrapers.py --only-updated

list:
	$(PY) scripts/admin_client.py list --state $(STATE)

scrape:
	$(PY) scripts/admin_client.py scrape --source-id $(SRC) --force=$(FORCE)
```

---

## Troubleshooting

* **`ModuleNotFoundError: settings`**
  Run uvicorn from the **repo root**:
  `python3 -m uvicorn app.main:app --reload`

* **404 on `/admin/scrape`**
  The `source_id` must match the exact file stem. Discover it via:
  `python3 scripts/admin_client.py list --state tx | jq -r '.[].source_id'`

* **Cache ENOENT (`last_signature.json`)**
  We use **per-scraper** caches now; re-generate scrapers and try with `force=true`, e.g.:
  `/admin/scrape-all?state=tx&pattern=fire&force=true`

* **PDF text empty**
  Try installing `pdfminer.six`, or check the PDF (scanned image vs text layer).

* **Windows venv activation**
  `.\.venv\Scripts\Activate.ps1` (PowerShell)

---

## Legal note

NFPA/IFC content is often paywalled. This project intentionally targets **public** artifacts (adoptions, rules incorporating by reference, notices, errata summaries) and **links** to authoritative sources. Do not scrape or redistribute paywalled code text.

---

## Roadmap (short)

* Wave A sourcing + scrapers + validation
* Minimal SQLite store + indexer (store `new_content`, URL, jurisdiction, timestamps)
* `/ask` route using retrieval (Gemini/ChatGPT) with source citations
* Alerting: Slack/Webhook with short summaries & impact hints
* Web dashboard + optional mobile app

---

*Questions / stuck on a source? Open an issue and tag it with `area:fire-codes`.*
