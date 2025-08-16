#!/bin/bash

# 🛢️ Query CalGEM Oil & Gas Wells (ArcGIS API)
# USAGE:
#   ./query_calgem_wells.sh "MIDWAY-SUNSET"
#   ./query_calgem_wells.sh "MIDWAY-SUNSET" "CALIFORNIA RESOURCES PROD"

BASE_URL="https://gis.conservation.ca.gov/server/rest/services/Well/MapServer/0/query"
FORMAT="json"
RETURN_GEOMETRY="false"
DATA_DIR="../../../../data"

FIELD_NAME="${1:-MIDWAY-SUNSET}"
OPERATOR_NAME="${2:-}"

WHERE="FIELD_NAME='${FIELD_NAME}'"
if [ -n "$OPERATOR_NAME" ]; then
  WHERE="${WHERE} AND OPERATOR='${OPERATOR_NAME}'"
fi

OUT_FIELDS="API,FIELD_NAME,OPERATOR,WELL_STATUS"
OUTPUT_FILE="${DATA_DIR}/calgem_${FIELD_NAME// /_}_response.json"

mkdir -p "$DATA_DIR"
echo "🔍 Querying CalGEM wells in '${FIELD_NAME}'"
[ -n "$OPERATOR_NAME" ] && echo "   Operator: $OPERATOR_NAME"

curl -sG "$BASE_URL" \
  --data-urlencode "where=$WHERE" \
  --data-urlencode "outFields=$OUT_FIELDS" \
  --data-urlencode "returnGeometry=$RETURN_GEOMETRY" \
  --data-urlencode "f=$FORMAT" \
  -o "$OUTPUT_FILE"

echo "✅ Results saved to $OUTPUT_FILE"
