#!/bin/bash

# ------------------------------------------------------------------------------
# Query Alaska DOG ArcGIS MapServer for oil & gas unit data (Layer 2)
#
# Usage:
#   ./query_dog_oil_gas_data.sh
#
# Description:
#   Sends a GET request to the DOG GIS API to fetch unit data based on a 
#   SQL-style WHERE clause (e.g. name contains "PRUDHOE").
#
# Requirements:
#   - curl
#   - jq (for pretty-printing JSON output)
#
# API Docs (ArcGIS-style):
#   https://dog.dnr.alaska.gov/arcgis/rest/services/DOG_GIS/DOG_GIS/MapServer/2/query
# ------------------------------------------------------------------------------

ENDPOINT="https://dog.dnr.alaska.gov/arcgis/rest/services/DOG_GIS/DOG_GIS/MapServer/2/query"

# Example WHERE clause: fetch units with "PRUDHOE" in the name
WHERE="UPPER(UnitName) LIKE '%PRUDHOE%'"

# Send request
curl -sG "$ENDPOINT" \
  --data-urlencode "where=$WHERE" \
  --data-urlencode "outFields=*" \
  --data-urlencode "returnGeometry=false" \
  --data-urlencode "f=json" \
  | jq .
