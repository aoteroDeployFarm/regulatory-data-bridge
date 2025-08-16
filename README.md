# Regulatory Data Bridge

This project integrates public and scraped data from federal and state regulatory agencies to monitor updates, provide insights, and interface with AI via OpenAPI specs.

## Structure

- `openapi/` – OpenAPI 3.1.0 specs for APIs (public and internal)
- `scrapers/` – Scraping logic for non-API websites
- `services/` – FastAPI service to expose scraper data
- `tests/` – Unit/integration tests
