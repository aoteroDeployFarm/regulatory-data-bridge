#!/bin/bash

echo "🛠️ Creating query scripts and data directory..."

# Base directories
BASE_DIR="regulatory-data-bridge/scripts/query"
DATA_DIR="regulatory-data-bridge/data"

# Create directory structure
mkdir -p "$BASE_DIR/arb"
mkdir -p "$BASE_DIR/ca_energy"
mkdir -p "$BASE_DIR/waterboards"
mkdir -p "$BASE_DIR/calgem"
mkdir -p "$DATA_DIR"

# ----------------------------
# ARB: LCFS Fuel Pathway Script
# ----------------------------
cat << 'EOF' > "$BASE_DIR/arb/query_arb_lcfs_pathways.sh"
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
EOF

# ----------------------------
# CA Energy: Power Plants Script
# ----------------------------
cat << 'EOF' > "$BASE_DIR/ca_energy/query_cec_power_plants.sh"
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
EOF

# ----------------------------
# Water Boards: Drinking Water Report Script
# ----------------------------
cat << 'EOF' > "$BASE_DIR/waterboards/query_waterboards_data.sh"
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
EOF

# ----------------------------
# CalGEM: Well Query Script
# ----------------------------
cat << 'EOF' > "$BASE_DIR/calgem/query_calgem_wells.sh"
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
EOF

# Make all scripts executable
chmod +x "$BASE_DIR"/**/*.sh

echo "✅ Query scripts and data directory created successfully."
