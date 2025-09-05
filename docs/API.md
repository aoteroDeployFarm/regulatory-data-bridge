# Regulatory Data Bridge — HTTP API

Version: `0.1.0`  
Base URL (local dev): `http://127.0.0.1:8000`

- Live docs (Swagger): `GET /docs`
- OpenAPI (JSON): `GET /openapi.json`
- Health check: `GET /health`

> The API uses **no auth** in dev. If you add auth later, document the header here (e.g., `X-API-Key`).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Endpoints](#endpoints)
  - [/scrapers](#getscrapers)
  - [/check-site-update](#getcheck-site-update)
  - [/batch-check](#getbatch-check)
  - [/metrics](#getmetrics)
  - [/health](#gethealth)
- [Response Schemas](#response-schemas)
- [Errors](#errors)
- [Settings & Env Vars](#settings--env-vars)
- [Filtering & One-liners](#filtering--one-liners)

---

## Quick Start

Run the API (factory pattern):

```bash
uvicorn services.web_api.app:create_app --factory --reload
````

Sanity checks:

```bash
curl -s http://127.0.0.1:8000/health | jq
curl -s http://127.0.0.1:8000/scrapers | jq
```

---

## Endpoints

### `GET /scrapers`

List all registered scraper anchors (keys). These keys are usually target URLs (or URL stems) that your scrapers monitor.

#### Request

```
GET /scrapers
```

#### Response `200 OK`

```json
{
  "count": 123,
  "keys": [
    "https://www.conservation.ca.gov/calgem",
    "https://www.epa.gov/npdes-permits/alabama-npdes-permits"
  ]
}
```

#### Notes

* Use these keys as inputs to `/check-site-update?url=...`.
* Keys are discovered at app startup by scanning `scrapers/**/check_updates.py` for `TARGET_URL`.

---

### `GET /check-site-update`

Run a single scraper by URL (or URL containing the key). The “best match” is chosen by **longest key substring**.

#### Request

```
GET /check-site-update?url=<absolute URL>
```

Examples:

```bash
curl -s --get "$API_URL/check-site-update" \
  --data-urlencode "url=https://www.conservation.ca.gov/calgem" | jq
```

#### Response `200 OK` (HTML-based scraper)

```json
{
  "url": "https://www.conservation.ca.gov/calgem",
  "updated": false,
  "lastChecked": "2025-08-25T19:03:42Z",
  "diffSummary": "No change"
}
```

#### Response `200 OK` (PDF-based scraper)

```json
{
  "url": "https://www.floridapsc.com/pscfiles/website-files/PDF/Utilities/Electricgas/GasSafety//RuleBookletCh25-2025.pdf",
  "updated": true,
  "diffSummary": "PDF signature changed"
}
```

#### Possible `4xx`

* `400` — No scraper registered for this URL.

---

### `GET /batch-check`

Execute **all** registered scrapers and return a consolidated report.

#### Request

```
GET /batch-check
```

#### Response `200 OK`

```json
{
  "count": 123,
  "results": [
    {
      "url": "https://www.conservation.ca.gov/calgem",
      "updated": false,
      "lastChecked": "2025-08-25T19:03:42Z",
      "diffSummary": "No change",
      "scraper": "https://www.conservation.ca.gov/calgem"
    },
    {
      "url": "https://www.epa.gov/npdes-permits/oregon-npdes-permits",
      "updated": true,
      "diffSummary": "Content hash changed",
      "scraper": "https://www.epa.gov/npdes-permits/oregon-npdes-permits"
    }
  ],
  "updated": 7,
  "errors": 1
}
```

#### Notes

* This endpoint increments internal run/update/error counters exposed at `/metrics`.

---

### `GET /metrics`

Simple counters since process start.

#### Request

```
GET /metrics
```

#### Response `200 OK`

```json
{
  "runs": 12,
  "updates": 19,
  "errors": 2
}
```

---

### `GET /health`

Basic health probe; includes environment and number of registered scrapers.

#### Request

```
GET /health
```

#### Response `200 OK`

```json
{
  "ok": true,
  "env": "dev",
  "scrapers": 123
}
```

---

## Response Schemas

### `/scrapers` — `GET`

```ts
type ScrapersResponse = {
  count: number;
  keys: string[]; // list of scraper anchors (usually absolute URLs)
}
```

### `/check-site-update` — `GET`

```ts
type CheckSiteUpdateResponse = {
  url: string;           // target url
  updated: boolean;      // whether content signature changed since last run
  diffSummary?: string;  // short reason; present on both HTML/PDF scrapers
  lastChecked?: string;  // ISO timestamp (present on HTML scrapers using _base helper)
}
```

### `/batch-check` — `GET`

```ts
type BatchCheckResponse = {
  count: number;         // total scrapers attempted
  results: Array<
    CheckSiteUpdateResponse & { scraper: string } // ‘scraper’ echoes the anchor key
  >;
  updated: number;       // number of updated==true in this run
  errors: number;        // number of scrapers that raised exceptions
}
```

### `/metrics` — `GET`

```ts
type MetricsResponse = {
  runs: number;    // how many times /batch-check has executed
  updates: number; // cumulative updated scrapers from all runs
  errors: number;  // cumulative scraper errors from all runs
}
```

### `/health` — `GET`

```ts
type HealthResponse = {
  ok: true;
  env: string;     // e.g., "dev" | "test" | "prod"
  scrapers: number;
}
```

---

## Errors

* `400 Bad Request` — No matching scraper for the provided URL (`/check-site-update`).
* `500 Internal Server Error` — Unexpected exception inside a scraper or the API.

Example error payload:

```json
{
  "detail": "No scraper registered for this URL"
}
```

---

## Settings & Env Vars

These are provided by `settings.py` (Pydantic Settings):

| Env Var            | Default | Description                                 |
| ------------------ | ------- | ------------------------------------------- |
| `RDB_ENV`          | `dev`   | Environment label (`dev`/`test`/`prod`)     |
| `RDB_TIMEOUT_SECS` | `15`    | Default HTTP timeout for scrapers (seconds) |

> Place a `.env` file at the repo root to override locally.

---

## Filtering & One-liners

List just the count:

```bash
curl -s "$API_URL/scrapers" | jq '.count'
```

List all keys (one per line):

```bash
curl -s "$API_URL/scrapers" | jq -r '.keys[]'
```

Filter by domain (example: `.ca.gov`):

```bash
curl -s "$API_URL/scrapers" | jq -r '.keys[] | select(contains(".ca.gov"))'
```

Batch-check only EPA NPDES pages:

```bash
curl -s "$API_URL/scrapers" \
| jq -r '.keys[] | select(test("epa\\.gov/npdes-permits"))' \
| while read -r URL; do
    curl -s --get "$API_URL/check-site-update" --data-urlencode "url=$URL";
  done \
| jq -s
```

Timing & status for `/scrapers`:

```bash
curl -s -o /dev/null -w "status=%{http_code} time=%{time_total}s\n" "$API_URL/scrapers"
```

---

## Changelog

* `0.1.0` — Initial public endpoints: `/scrapers`, `/check-site-update`, `/batch-check`, `/metrics`, `/health`.

```

If you want, I can also generate `docs/curl-scrapers.md` with more shell recipes, or wire a Redoc page at `/redoc` that reads from `/openapi.json`.
```
