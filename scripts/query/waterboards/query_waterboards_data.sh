#!/bin/bash

# 🚰 Query Water Boards Annual Drinking Water Report
# USAGE:
#   ./query_waterboards_data.sh "Los Angeles"
#   ./query_waterboards_data.sh "San Diego" 10

BASE_URL="https://data.ca.gov/api/3/action/datastore_search"
RESOURCE_ID="36ec1a68-4a1a-45b3-9fd1-4f7613bb4f04"
DATA_DIR="../../../../data"

QUERY="${1:-Los Angeles}"
LIMIT="${2:-10}"
OUTPUT_FILE="${DATA_DIR}/waterboards_${QUERY// /_}.json"

mkdir -p "$DATA_DIR"
echo "🔍 Querying Water Boards: $QUERY (limit: $LIMIT)"
curl -sG "$BASE_URL" \
  --data-urlencode "resource_id=$RESOURCE_ID" \
  --data-urlencode "q=$QUERY" \
  --data-urlencode "limit=$LIMIT" \
  -o "$OUTPUT_FILE"

echo "✅ Results saved to $OUTPUT_FILE"
