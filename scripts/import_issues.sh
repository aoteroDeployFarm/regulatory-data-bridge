#!/usr/bin/env bash
set -euo pipefail

# Requires:
#  - gh (GitHub CLI): https://cli.github.com/
#  - jq: https://stedolan.github.io/jq/
# Usage:
#  ./scripts/import_issues.sh [path/to/issues.json]
#
# Notes:
# - Creates milestones if missing.
# - Creates labels if missing (default color if needed).
# - Creates issues with titles, bodies, labels, and milestones.

ISSUES_JSON="${1:-data/issues.json}"

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI not found. Install from https://cli.github.com/" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq not found. Install with 'brew install jq' (macOS) or your package manager." >&2
  exit 1
fi

if [ ! -f "$ISSUES_JSON" ]; then
  echo "ERROR: File not found: $ISSUES_JSON" >&2
  exit 1
fi

# Ensure we're authenticated
gh auth status || {
  echo "You must authenticate: gh auth login" >&2
  exit 1
}

# Detect current repo (owner/name)
REPO_JSON=$(gh repo view --json owner,name 2>/dev/null)
OWNER=$(echo "$REPO_JSON" | jq -r '.owner.login')
REPO=$(echo "$REPO_JSON" | jq -r '.name')
FULL_REPO="$OWNER/$REPO"
echo "Using repo: $FULL_REPO"

# Gather unique milestones & labels from JSON
MILESTONES=($(jq -r '.issues[].milestone' "$ISSUES_JSON" | sort -u | sed '/^null$/d'))
LABELS=($(jq -r '.issues[].labels[]?' "$ISSUES_JSON" | sort -u))

# Fetch existing milestones & labels
EXISTING_MILESTONES=$(gh api "repos/$FULL_REPO/milestones?state=all" --paginate | jq -r '.[].title' | sort -u || true)
EXISTING_LABELS=$(gh api "repos/$FULL_REPO/labels?per_page=100" --paginate | jq -r '.[].name' | sort -u || true)

# Helper: test membership
in_list () { echo "$1" | grep -Fxq "$2"; }

echo "== Ensuring milestones exist =="
for ms in "${MILESTONES[@]}"; do
  if ! in_list "$EXISTING_MILESTONES" "$ms"; then
    echo "Creating milestone: $ms"
    gh api -X POST "repos/$FULL_REPO/milestones" -f title="$ms" >/dev/null
  else
    echo "Milestone exists: $ms"
  fi
done

# Refresh milestone list after possible creations
EXISTING_MILESTONES=$(gh api "repos/$FULL_REPO/milestones?state=all" --paginate | jq -r '.[].title' | sort -u || true)

# Label color to use if creating new labels (hex without #)
DEFAULT_LABEL_COLOR="0E8A16"

echo "== Ensuring labels exist =="
for lbl in "${LABELS[@]}"; do
  if ! in_list "$EXISTING_LABELS" "$lbl"; then
    echo "Creating label: $lbl"
    gh api -X POST "repos/$FULL_REPO/labels" \
      -f name="$lbl" \
      -f color="$DEFAULT_LABEL_COLOR" >/dev/null || true
  else
    echo "Label exists: $lbl"
  fi
done

echo "== Creating issues =="
LEN=$(jq '.issues | length' "$ISSUES_JSON")
for i in $(seq 0 $((LEN-1))); do
  TITLE=$(jq -r ".issues[$i].title" "$ISSUES_JSON")
  BODY=$(jq -r ".issues[$i].body" "$ISSUES_JSON")
  MILESTONE=$(jq -r ".issues[$i].milestone // empty" "$ISSUES_JSON")
  LABELS_LIST=$(jq -r ".issues[$i].labels // [] | join(\",\")" "$ISSUES_JSON")

  echo "Creating: $TITLE"
  # Build args
  ARGS=(issue create --title "$TITLE" --body "$BODY")
  [ -n "$LABELS_LIST" ] && ARGS+=(--label "$LABELS_LIST")
  [ -n "$MILESTONE" ] && ARGS+=(--milestone "$MILESTONE")

  gh "${ARGS[@]}" >/dev/null
done

echo "Done."
