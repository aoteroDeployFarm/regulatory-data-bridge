#!/bin/bash

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
