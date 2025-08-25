# Regulatory Data Bridge — cURL Guide

Set a base URL (local by default):

```bash
export API_URL="http://127.0.0.1:8000"
# optional: install jq for pretty output
#   macOS:  brew install jq
#   Ubuntu: sudo apt-get update && sudo apt-get install -y jq
```

## List all registered scrapers

```bash
curl -s "$API_URL/scrapers" | jq
```

**Response shape:**

```json
{
  "count": 123,
  "keys": [
    "https://www.conservation.ca.gov/calgem",
    "https://www.epa.gov/npdes-permits/...",
    "... more ..."
  ]
}
```

### Just the count

```bash
curl -s "$API_URL/scrapers" | jq '.count'
```

### Show keys only (one per line)

```bash
curl -s "$API_URL/scrapers" | jq -r '.keys[]'
```

### Filter scrapers by domain substring

```bash
# All California .ca.gov sites
curl -s "$API_URL/scrapers" | jq -r '.keys[] | select(test("ca\\.gov"))'

# Only EPA NPDES pages
curl -s "$API_URL/scrapers" | jq -r '.keys[] | select(test("epa\\.gov/npdes-permits"))'
```

---

## Check a single site

Use `/check-site-update?url=...`. Let `curl` URL-encode the parameter:

```bash
curl -s --get "$API_URL/check-site-update" --data-urlencode "url=https://www.conservation.ca.gov/calgem" | jq
```

**Typical response:**

```json
{
  "url": "https://www.conservation.ca.gov/calgem",
  "updated": false,
  "lastChecked": "2025-08-25T19:03:42Z",
  "diffSummary": "No change"
}
```

---

## Batch check all scrapers

```bash
curl -s "$API_URL/batch-check" | jq
```

**Response shape:**

```json
{
  "count": 123,
  "results": [ { "url": "...", "updated": true }, ... ],
  "updated": 7,
  "errors": 1
}
```

### Batch check a filtered subset (e.g., only `ca.gov`)

```bash
curl -s "$API_URL/scrapers" \
| jq -r '.keys[] | select(test("ca\\.gov"))' \
| while read -r URL; do
    curl -s --get "$API_URL/check-site-update" --data-urlencode "url=$URL";
  done \
| jq -s  # collect into a JSON array
```

---

## Health & metrics

```bash
# health
curl -s "$API_URL/health" | jq
# metrics (runs/updates/errors counters)
curl -s "$API_URL/metrics" | jq
```

---

## Helpful curl flags

* `-s` silent (no progress bar), `-S` show errors
* `-i` include response headers
* `--get --data-urlencode "url=..."` safely encodes query strings
* `-w` format timing/status info:

  ```bash
  curl -s -o /dev/null -w "status=%{http_code} time=%{time_total}s\n" "$API_URL/scrapers"
  ```

---

## Troubleshooting

* **404/400** on `/check-site-update`: the URL isn’t registered. First, list `/scrapers` and copy a key exactly.
* **Empty `/scrapers`**: ensure the app started with discovery:

  ```bash
  uvicorn services.web_api.app:create_app --factory --reload
  ```
* **Unicode/regex in `jq`**: escape dots in domain filters (`epa\.gov`), or use `contains("epa.gov")` instead of `test(...)`.

---

### Quick copy/paste block

```bash
# List
curl -s "$API_URL/scrapers" | jq
# Count
curl -s "$API_URL/scrapers" | jq '.count'
# One URL
curl -s --get "$API_URL/check-site-update" --data-urlencode "url=https://www.conservation.ca.gov/calgem" | jq
# Batch
curl -s "$API_URL/batch-check" | jq '.updated,.errors'
```

---

If you want, I can generate a `docs/API.md` that includes these plus OpenAPI snippets for each route.
