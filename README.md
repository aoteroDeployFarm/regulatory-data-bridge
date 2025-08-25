# Regulatory Data Bridge

Aggregate regulatory data from public APIs and high-signal web pages. This repo includes:

* **OpenAPI specs** for federal/state data sources
* **Scrapers** for sites without APIs (with auto-discovery & caching)
* A **FastAPI** microservice to run scrapers and expose results
* **CI** to test scrapers and lint specs
* **Generator scripts** to scaffold lots of state scrapers from a JSON list

## Table of Contents

- [Regulatory Data Bridge](#regulatory-data-bridge)
  - [Table of Contents](#table-of-contents)
  - [Quick Start](#quick-start)
  - [Repository Layout](#repository-layout)
  - [Run the API](#run-the-api)
  - [cURL \& Endpoints](#curl--endpoints)
  - [Scraper Discovery (How it works)](#scraper-discovery-how-it-works)
  - [Generate Scrapers in Bulk](#generate-scrapers-in-bulk)
  - [Testing](#testing)
  - [CI \& Automation](#ci--automation)
  - [Docker](#docker)
  - [Configuration](#configuration)
  - [Troubleshooting](#troubleshooting)
  - [License](#license)

---

## Quick Start

> Requires **Python 3.11+**.

```bash
# from repo root
python -m venv .venv
source .venv/bin/activate

# install service + dev deps
pip install -r services/web_api/requirements.txt -r requirements-dev.txt
# If you see pydantic BaseSettings errors, also:
pip install pydantic>=2.7 pydantic-settings>=2.3

# run tests
pytest -q

# run API (factory pattern)
uvicorn services.web_api.app:create_app --factory --reload
# → http://127.0.0.1:8000/health
```

Helpful docs:

* API guide: `docs/API.md`
* cURL recipes: `docs/curl-scrapers.md`

---

## Repository Layout

```
.
├── openapi/                     # OpenAPI 3.1 specs (federal + states + internal)
│   ├── federal/…
│   ├── states/…
│   └── internal/scrapedUpdates.yaml
├── scrapers/                    # Website scrapers
│   ├── _base.py                 # shared helpers (diffing, caching)
│   ├── federal/<agency>/check_updates.py
│   └── state/<xx>/<domain_slug>/check_updates.py
├── services/
│   └── web_api/                 # FastAPI service
│       ├── app.py               # create_app() + lifespan
│       ├── registry.py          # auto-discovers scrapers
│       ├── routes/
│       │   ├── updates.py       # /scrapers, /check-site-update, /batch-check
│       │   └── metrics.py       # /metrics
│       ├── settings.py          # pydantic-settings config
│       └── requirements.txt
├── shared/
│   ├── http.py                  # shared httpx client + retry/backoff
│   └── logging.py               # JSON logging setup
├── scripts/
│   ├── generate_scrapers_from_json.py   # bulk scaffold from state JSON
│   └── query/*                   # sample scripts for API sources
├── state-website-data/state-website-data.json
├── tests/
│   ├── test_scrapers/*           # import/run smoke tests per scraper
│   └── test_package_integrity.py # sanity (no legacy paths, all importable)
├── .github/workflows/            # CI & scheduled runs
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml                # pytest config (paths, -q)
├── requirements-dev.txt
└── README.md
```

> Note: A couple legacy top-level folders like `scrapers/conservation.ca.gov/` may exist. They’re ignored unless they contain `__init__.py`. New scrapers should live under `scrapers/state/<xx>/<domain_slug>/`.

---

## Run the API

Local dev (recommended):

```bash
uvicorn services.web_api.app:create_app --factory --reload
```

Endpoints:

* `GET /health` – service health + scraper count
* `GET /scrapers` – list registered scraper anchors (keys)
* `GET /check-site-update?url=<absolute URL>` – run best-match scraper
* `GET /batch-check` – run all scrapers
* `GET /metrics` – simple counters (runs/updates/errors)

See **`docs/API.md`** for full response shapes and examples.

---

## cURL & Endpoints

Quick examples:

```bash
export API_URL="http://127.0.0.1:8000"

# list scrapers
curl -s "$API_URL/scrapers" | jq

# run one
curl -s --get "$API_URL/check-site-update" \
  --data-urlencode "url=https://www.conservation.ca.gov/calgem" | jq

# batch
curl -s "$API_URL/batch-check" | jq '.updated,.errors'
```

More recipes: **`docs/curl-scrapers.md`**

---

## Scraper Discovery (How it works)

The service auto-registers scrapers at startup:

* It walks `scrapers/**/check_updates.py`.
* Each module must export:

  * `TARGET_URL: str`
  * `check_for_update() -> dict` (returns at least `{"url": ..., "updated": bool}`)
  * (HTML scrapers typically also define `fetch_html()` and use `_base.check_updated()`.)

Router behavior:

* `/scrapers` returns discovered **keys** (usually the `TARGET_URL` value).
* `/check-site-update?url=…` picks the **longest substring match** among keys to choose the scraper (specific > generic).

Caching:

* Each scraper writes a small signature/HTML cache under `…/.cache/` to detect changes between runs.

---

## Generate Scrapers in Bulk

Use the JSON list at `state-website-data/state-website-data.json` to scaffold many scrapers:

```bash
# dry run (no files written)
python scripts/generate_scrapers_from_json.py --dry-run

# generate for all states
python scripts/generate_scrapers_from_json.py

# subset, limit per state, custom selectors file
python scripts/generate_scrapers_from_json.py -s CA CO --max-per-state 10 \
  --selectors-file state-website-data/selectors.json
```

The generator:

* Creates `scrapers/state/<xx>/<domain_slug>/check_updates.py`.
* Emits a matching test in `tests/test_scrapers/…`.
* Detects **PDF** URLs and builds a header/hash signature checker.
* For HTML, uses a default CSS selector (override per domain via `selectors.json`).

---

## Testing

```bash
# local
pytest -q

# config is in pyproject.toml
# pythonpath is ".", tests live under tests/test_scrapers
```

Each generated scraper has a smoke test that mocks `fetch_html()` and asserts the result shape.

---

## CI & Automation

GitHub Actions:

* **CI** (`.github/workflows/ci.yml`)

  * Installs service + dev deps
  * Runs `pytest -q`
  * Lints OpenAPI specs with Redocly
* **OpenAPI validation** (`validate-openapi.yml`) – standalone lint run
* **Weekday batch check** (`batch-check.yml`)

  * Triggers at `13:00Z` *and* `14:00Z`
  * Guards to only run when it’s **07:00 America/Denver**
  * Posts a Slack summary (`RDB_API_URL`, `SLACK_WEBHOOK` repo secrets)

> **Heads up:** In CI, make sure the path is `services/web_api/requirements.txt` (underscore). If your workflow still references `services/web-api/…` (hyphen), update it.

---

## Docker

**docker-compose (dev):**

```yaml
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    volumes:
      - ./.data_cache:/app/scrapers
```

**Dockerfile (update these if needed):**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/web_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
# Use factory entrypoint
CMD ["uvicorn", "services.web_api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:

```bash
docker compose up --build
# → http://localhost:8000/health
```

---

## Configuration

Environment variables (via `pydantic-settings`):

| Var                | Default | Notes                             |        |          |
| ------------------ | ------- | --------------------------------- | ------ | -------- |
| `RDB_ENV`          | `dev`   | \`"dev"                           | "test" | "prod"\` |
| `RDB_TIMEOUT_SECS` | `15`    | Default HTTP timeout for scrapers |        |          |

Create a `.env` at repo root to override locally.

---

## Troubleshooting

**No `BaseSettings` in pydantic**
Install pydantic v2 and pydantic-settings:

```bash
pip install "pydantic>=2.7" "pydantic-settings>=2.3"
```

**`ModuleNotFoundError: services.web_api` or router import errors**
Ensure package markers exist:

```bash
touch services/__init__.py services/web_api/__init__.py services/web_api/routes/__init__.py
touch scrapers/__init__.py scrapers/federal/__init__.py
# (state packages are created by the generator)
find . -name "__pycache__" -type d -exec rm -rf {} +
```

Run the **factory** entrypoint:

```bash
uvicorn services.web_api.app:create_app --factory --reload
```

**Docker/CI still using `services/web-api` (hyphen)**
Update to `services/web_api` (underscore) and use the factory command in `CMD`.

**/check-site-update returns 400**
The URL you passed isn’t matched by any **key**. List keys:

```bash
curl -s http://127.0.0.1:8000/scrapers | jq -r '.keys[]'
```

---

## License

MIT © Contributors


