#!/bin/bash
# create_alaska_scraper_dirs.sh — Bootstrap Alaska-specific scraper directories.
#
# Place at: tools/create_alaska_scraper_dirs.sh
# Run from the repo root.
#
# What this does:
#   - Creates subdirectories under scrapers/states/ak for various Alaska regulators.
#   - Ensures each has a .cache/ subfolder (for scraper state/signatures).
#   - Skips creation if the directory already exists.
#
# Target directories:
#   - aogcc
#   - dnr-dog
#   - dnr-dog-lease
#   - dec-air
#   - dec-water
#   - dec-contingency
#   - epa-npdes-ak
#   - rca
#
# Common examples:
#   ./tools/create_alaska_scraper_dirs.sh
#       # Create scrapers/states/ak/<agency>/ with .cache/ inside each
#
# Notes:
#   - Safe to run multiple times; existing folders are left intact.
#   - Extend AK_DIRS array if new Alaska agencies need scrapers.
#

# Create folders for Alaska regulatory sites under scrapers/states/ak
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../" && pwd)"
DEST="$ROOT_DIR/scrapers/states/ak"

mkdir -p "$DEST"

# List of directories to create
AK_DIRS=(
  "aogcc"
  "dnr-dog"
  "dnr-dog-lease"
  "dec-air"
  "dec-water"
  "dec-contingency"
  "epa-npdes-ak"
  "rca"
)

echo "📁 Creating Alaska scraper folders in: $DEST"
echo "----------------------------------------"

for NAME in "${AK_DIRS[@]}"; do
  TARGET="$DEST/$NAME"
  if [ ! -d "$TARGET" ]; then
    mkdir -p "$TARGET/.cache"
    echo "✅ Created: $TARGET"
  else
    echo "⚠️  Already exists: $TARGET"
  fi
done

echo "✅ All Alaska scraper folders are ready."
