#!/bin/bash
# validate-openapi.sh — Validate all OpenAPI spec files in the repo using Redocly CLI.
#
# Place at: tools/validate-openapi.sh
# Run from the repo root (folder that contains openapi/).
#
# What this does:
#   - Finds every *.yaml file under the openapi/ directory.
#   - Runs `npx @redocly/cli lint` against each file to check for spec compliance.
#
# Prereqs:
#   - Node.js installed
#   - @redocly/cli available (auto-installed on first run via npx)
#
# Common examples:
#   ./tools/validate-openapi.sh
#       # Validate all specs in openapi/, printing lint results for each
#
# Notes:
#   - Exits with the status of the last lint command (nonzero if any spec fails).
#   - You can install @redocly/cli globally to speed up repeated runs:
#       npm install -g @redocly/cli
#

echo "🔍 Validating all OpenAPI specs..."
for file in $(find openapi -name "*.yaml"); do
  echo "Validating: $file"
  npx @redocly/cli lint "$file"
done
