#!/bin/bash

# 🔌 Query CEC Power Plant Data from data.ca.gov
# USAGE:
#   ./query_cec_power_plants.sh "Los Angeles"
#   ./query_cec_power_plants.sh "Sacramento" 5

BASE_URL="https://data.ca.gov/api/3/action/datastore_search"
RESOURCE_ID="a831da55-3212-4eb4-90a0-f53a5b48a51e"
DATA_DIR="../../../../data"

QUERY="${1:-Los Angeles}"
LIMIT="${2:-10}"
OUTPUT_FILE="${DATA_DIR}/cec_powerplants_${QUERY// /_}.json"

mkdir -p "$DATA_DIR"
echo "🔍 Querying CEC Power Plants: $QUERY (limit: $LIMIT)"
curl -sG "$BASE_URL" \
  --data-urlencode "resource_id=$RESOURCE_ID" \
  --data-urlencode "q=$QUERY" \
  --data-urlencode "limit=$LIMIT" \
  -o "$OUTPUT_FILE"

echo "✅ Results saved to $OUTPUT_FILE"
