#!/bin/bash

echo "🛠️ Creating project structure for regulatory-data-bridge..."

# Directory structure
mkdir -p openapi/epa
mkdir -p openapi/phmsa
mkdir -p openapi/ca/conservation
mkdir -p openapi/internal
mkdir -p openapi/shared-components

mkdir -p scrapers/common
mkdir -p scrapers/ferc.gov
mkdir -p scrapers/boem.gov
mkdir -p scrapers/cpuc.ca.gov
mkdir -p scrapers/energy.ca.gov
mkdir -p scrapers/waterboards.ca.gov

mkdir -p services/web-api/routes

mkdir -p tests/test_scrapers
mkdir -p tests/test_openapi

mkdir -p scripts

mkdir -p .github/workflows

# Top-level files
cat << EOF > README.md
# Regulatory Data Bridge

This project integrates public and scraped data from federal and state regulatory agencies to monitor updates, provide insights, and interface with AI via OpenAPI specs.

## Structure

- \`openapi/\` – OpenAPI 3.1.0 specs for APIs (public and internal)
- \`scrapers/\` – Scraping logic for non-API websites
- \`services/\` – FastAPI service to expose scraper data
- \`tests/\` – Unit/integration tests
EOF

echo "MIT" > LICENSE

cat << EOF > .gitignore
__pycache__/
.env
*.pyc
*.log
.cache/
.DS_Store
venv/
EOF

# Example OpenAPI spec for EPA
cat << 'EOF' > openapi/epa/envirofacts.yaml
openapi: 3.1.0
info:
  title: EPA Envirofacts API
  description: >
    Access environmental facility data from EPA's Envirofacts system.
  version: 1.0.0
servers:
  - url: https://enviro.epa.gov/enviro/efservice
    description: EPA Envirofacts service
paths:
  /facility/{column_name}/{value}/JSON:
    get:
      operationId: getFacilityByField
      summary: Get facilities by column and value
      parameters:
        - name: column_name
          in: path
          required: true
          schema:
            type: string
        - name: value
          in: path
          required: true
          schema:
            type: string
      responses:
        '200':
          description: List of matching facilities
          content:
            application/json:
              schema:
                type: array
                items:
                  type: object
EOF

# FastAPI starter app
cat << 'EOF' > services/web-api/app.py
from fastapi import FastAPI
from routes import updates

app = FastAPI(title="Scraper Service API")

app.include_router(updates.router)

@app.get("/")
def read_root():
    return {"message": "Scraper Service is running"}
EOF

# Route file placeholder
mkdir -p services/web-api/routes
cat << 'EOF' > services/web-api/routes/updates.py
from fastapi import APIRouter

router = APIRouter()

@router.get("/check-site-update")
def check_site_update(url: str):
    # TODO: Replace with real scraper logic
    return {
        "url": url,
        "updated": True,
        "lastChecked": "2025-08-16T12:00:00Z",
        "diffSummary": "Detected text change in main content area."
    }
EOF

# Requirements file
cat << EOF > services/web-api/requirements.txt
fastapi
uvicorn
beautifulsoup4
httpx
EOF

# GitHub Actions workflow for validating specs
cat << 'EOF' > .github/workflows/validate-openapi.yml
name: Validate OpenAPI Specs

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install Redocly CLI
        run: npm install -g @redocly/cli
      - name: Lint OpenAPI Specs
        run: |
          for file in $(find openapi -name "*.yaml"); do
            echo "🔍 Validating: $file"
            npx @redocly/cli lint "$file"
          done
EOF

# Validation script
cat << 'EOF' > scripts/validate-openapi.sh
#!/bin/bash
echo "🔍 Validating all OpenAPI specs..."
for file in $(find openapi -name "*.yaml"); do
  echo "Validating: $file"
  npx @redocly/cli lint "$file"
done
EOF
chmod +x scripts/validate-openapi.sh

# Folder readmes
echo "# EPA OpenAPI specs" > openapi/epa/readme.md
echo "# Internal APIs for scraped content" > openapi/internal/readme.md

echo "✅ Project structure and starter files created successfully."
