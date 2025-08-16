#!/bin/bash

# ⚗️  Query CARB LCFS Fuel Pathway Table from data.ca.gov
# USAGE:
#   ./query_arb_lcfs_pathways.sh "Ethanol"
#   ./query_arb_lcfs_pathways.sh "Biodiesel" 5

BASE_URL="https://data.ca.gov/api/3/action/datastore_search"
RESOURCE_ID="7e7c3f4a-c0a1-4601-a210-b638729b2d2d"
DATA_DIR="../../../../data"

QUERY="${1:-Ethanol}"
LIMIT="${2:-10}"
OUTPUT_FILE="${DATA_DIR}/carb_lcfs_${QUERY// /_}.json"

mkdir -p "$DATA_DIR"
echo "🔍 Querying CARB LCFS Fuel Pathways: $QUERY (limit: $LIMIT)"
curl -sG "$BASE_URL" \
  --data-urlencode "resource_id=$RESOURCE_ID" \
  --data-urlencode "q=$QUERY" \
  --data-urlencode "limit=$LIMIT" \
  -o "$OUTPUT_FILE"

echo "✅ Results saved to $OUTPUT_FILE"
