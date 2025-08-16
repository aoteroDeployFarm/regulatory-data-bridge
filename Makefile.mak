# ================================================
# 📦 Makefile for Querying Regulatory Data
# ================================================

SHELL := /bin/bash

# Paths to scripts
ARB_SCRIPT := scripts/query/arb/query_arb_lcfs_pathways.sh
CEC_SCRIPT := scripts/query/ca_energy/query_cec_power_plants.sh
WB_SCRIPT  := scripts/query/waterboards/query_waterboards_data.sh
CALGEM_SCRIPT := scripts/query/calgem/query_calgem_wells.sh

DATA_DIR := data

# ================================================
# 🧰 Usage Guide
# ================================================
.PHONY: help
help:
	@echo ""
	@echo "🚀 Usage: make [command]"
	@echo ""
	@echo "Commands:"
	@echo "  help               Show this usage guide"
	@echo ""
	@echo "  fetch-arb          Query CARB LCFS Fuel Pathways dataset (default: Ethanol)"
	@echo "  fetch-cec          Query CA Energy Commission Power Plants (default: Los Angeles)"
	@echo "  fetch-waterboard   Query CA Water Boards Drinking Water Report (default: Fresno)"
	@echo "  fetch-calgem       Query CalGEM oil & gas wells (default: MIDWAY-SUNSET)"
	@echo ""
	@echo "  fetch-all          Run all the above queries"
	@echo ""
	@echo "🗂  Output will be saved to: $(DATA_DIR)/"
	@echo ""

# ================================================
# 🛠️ Individual Data Fetch Commands
# ================================================

.PHONY: fetch-arb
fetch-arb:
	@$(ARB_SCRIPT) "Ethanol" 10

.PHONY: fetch-cec
fetch-cec:
	@$(CEC_SCRIPT) "Los Angeles" 10

.PHONY: fetch-waterboard
fetch-waterboard:
	@$(WB_SCRIPT) "Fresno" 10

.PHONY: fetch-calgem
fetch-calgem:
	@$(CALGEM_SCRIPT) "MIDWAY-SUNSET" "CALIFORNIA RESOURCES PROD"

# ================================================
# 🧪 Run All
# ================================================

.PHONY: fetch-all
fetch-all: fetch-arb fetch-cec fetch-waterboard fetch-calgem
	@echo ""
	@echo "✅ All queries completed. Check the $(DATA_DIR)/ directory."
