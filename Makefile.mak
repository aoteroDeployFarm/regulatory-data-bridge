# ================================================
# 📦 Makefile — Regulatory Data Bridge (Dev + Queries)
# ================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

# -------- Paths (existing external query scripts) --------
ARB_SCRIPT      := scripts/query/arb/query_arb_lcfs_pathways.sh
CEC_SCRIPT      := scripts/query/ca_energy/query_cec_power_plants.sh
WB_SCRIPT       := scripts/query/waterboards/query_waterboards_data.sh
CALGEM_SCRIPT   := scripts/query/calgem/query_calgem_wells.sh

DATA_DIR := data
LOG_DIR  := logs

# -------- Python / API tooling --------
VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
UV      := $(VENV)/bin/uvicorn

API_BASE ?= http://127.0.0.1:8000

# ================================================
# 🧰 Usage Guide
# ================================================
.PHONY: help
help:
	@echo ""
	@echo "🚀 Usage: make <command>"
	@echo ""
	@echo "Dev / Ops:"
	@echo "  deps                    Create venv (if missing) + install base deps"
	@echo "  api                     Run FastAPI with reload (port 8000)"
	@echo "  index                   Create helpful DB index on document_versions"
	@echo "  ingest-co               Ingest Colorado (auto-detects /admin method)"
	@echo "  changes-json            Show recent CO changes (7d window)"
	@echo "  changes-csv             Download CO changes CSV (7d window)"
	@echo "  digest-co-incremental   Run email digest for CO with since-file + log"
	@echo "  openapi-paths           List mounted API paths from openapi.json"
	@echo ""
	@echo "External data fetchers (existing):"
	@echo "  fetch-arb               CARB LCFS Fuel Pathways (default: Ethanol)"
	@echo "  fetch-cec               CA Energy Commission Power Plants (Los Angeles)"
	@echo "  fetch-waterboard        CA Water Boards Drinking Water Report (Fresno)"
	@echo "  fetch-calgem            CalGEM oil & gas wells (MIDWAY-SUNSET)"
	@echo "  fetch-all               Run all above queries"
	@echo ""
	@echo "🗂  Output lives in: $(DATA_DIR)/   📜 Logs: $(LOG_DIR)/"
	@echo ""

# ================================================
# 🔧 Dev / Ops
# ================================================

$(VENV):
	python3 -m venv $(VENV)

.PHONY: deps
deps: $(VENV)
	@mkdir -p $(LOG_DIR)
	$(PIP) install -U pip wheel
	# If your repo uses requirements.txt or a package install, uncomment one:
	# $(PIP) install -r requirements.txt
	# $(PIP) install -e .
	# admin client uses requests:
	$(PIP) install requests

.PHONY: api
api:
	$(UV) app.main:app --reload --port 8000

.PHONY: index
index:
	sqlite3 dev.db "CREATE INDEX IF NOT EXISTS ix_doc_versions_change_time ON document_versions(change_type, fetched_at DESC);"

# Uses tools/admin_client.py to auto-detect GET/POST for /admin/ingest (or /admin/scrape-all)
.PHONY: ingest-co
ingest-co:
	$(PY) tools/admin_client.py ingest --base $(API_BASE) --state co --limit 25 --force | jq .

# Handy debugging helpers for /changes once the router is added
.PHONY: changes-json
changes-json:
	curl -s "$(API_BASE)/changes?jurisdiction=CO&since=$$(date -v-7d +%F)" | jq .

.PHONY: changes-csv
changes-csv:
	curl -s "$(API_BASE)/changes/export.csv?jurisdiction=CO&since=$$(date -v-7d +%F)" | head -n 20

# Email digest (CSV attach logic lives inside tools/send_digest.py)
.PHONY: digest-co-incremental
digest-co-incremental:
	@mkdir -p $(LOG_DIR)
	$(PY) tools/send_digest.py --jur CO --since-file .digest_since_co.txt --to customer@example.com | tee -a $(LOG_DIR)/digest.log

# Show what routes are actually mounted
.PHONY: openapi-paths
openapi-paths:
	curl -s "$(API_BASE)/openapi.json" | jq '.paths | keys'

# ================================================
# 🌐 External Data Fetch Commands (existing)
# ================================================

.PHONY: fetch-arb
fetch-arb:
	@mkdir -p $(DATA_DIR)
	@$(ARB_SCRIPT) "Ethanol" 10

.PHONY: fetch-cec
fetch-cec:
	@mkdir -p $(DATA_DIR)
	@$(CEC_SCRIPT) "Los Angeles" 10

.PHONY: fetch-waterboard
fetch-waterboard:
	@mkdir -p $(DATA_DIR)
	@$(WB_SCRIPT) "Fresno" 10

.PHONY: fetch-calgem
fetch-calgem:
	@mkdir -p $(DATA_DIR)
	@$(CALGEM_SCRIPT) "MIDWAY-SUNSET" "CALIFORNIA RESOURCES PROD"

# ================================================
# 🧪 Run All External Fetches
# ================================================

.PHONY: fetch-all
fetch-all: fetch-arb fetch-cec fetch-waterboard fetch-calgem
	@echo ""
	@echo "✅ All queries completed. Check the $(DATA_DIR)/ directory."
