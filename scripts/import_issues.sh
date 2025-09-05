#!/usr/bin/env bash
set -euo pipefail

# Requires:
#   - gh (GitHub CLI): https://cli.github.com/
#   - jq: https://stedolan.github.io/jq/
# Usage:
#   ./scripts/import_issues.sh [data/issues.json]
#
# Notes:
# - Compatible with macOS Bash 3 (no 'mapfile').
# - Preserves spaces in milestone titles and labels.
# - Creates milestones & labels if missing.
# - Skips creating an issue if a title already exists (state:any).

ISSUES_JSON="${1:-data/issues.json}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: '$1' not found"; exit 1; }; }
need gh
need jq

[ -f "$ISSUES_JSON" ] || { echo "ERROR: File not found: $ISSUES_JSON" >&2; exit 1; }

# Ensure we're authenticated
if ! gh auth status >/dev/null 2>&1; then
  echo "You must authenticate: gh auth login" >&2
  exit 1
fi

# Detect current repo
REPO_JSON=$(gh repo view --json owner,name 2>/dev/null)
OWNER=$(echo "$REPO_JSON" | jq -r '.owner.login')
REPO=$(echo "$REPO_JSON" | jq -r '.name')
FULL_REPO="$OWNER/$REPO"
echo "Using repo: $FULL_REPO"

# ---- Collect unique milestones (newline list; preserve spaces) ----
MILESTONES=$(
  jq -r '.issues[].milestone // empty' "$ISSUES_JSON" \
  | sed '/^$/d' \
  | sort -u
)

# ---- Collect unique labels (newline list; preserve spaces) ----
ALL_LABELS=$(
  jq -r '.issues[].labels[]? // empty' "$ISSUES_JSON" \
  | sed '/^$/d' \
  | sort -u
)

# ---- Fetch existing milestones & labels ----
EXISTING_MILESTONES=$(
  gh api "repos/$FULL_REPO/milestones?state=all&per_page=100" --paginate \
  | jq -r '.[].title' | sort -u
)
EXISTING_LABELS=$(
  gh api "repos/$FULL_REPO/labels?per_page=100" --paginate \
  | jq -r '.[].name' | sort -u
)

echo "== Ensuring milestones exist =="
IFS=$'\n'
for ms in $MILESTONES; do
  [ -z "$ms" ] && continue
  if ! grep -Fxq -- "$ms" <<< "$EXISTING_MILESTONES"; then
    echo "Creating milestone: $ms"
    gh api -X POST "repos/$FULL_REPO/milestones" -f title="$ms" >/dev/null
    EXISTING_MILESTONES=$(printf "%s\n%s\n" "$EXISTING_MILESTONES" "$ms" | sort -u)
  else
    echo "Milestone exists: $ms"
  fi
done

DEFAULT_LABEL_COLOR="0E8A16"

echo "== Ensuring labels exist =="
for lbl in $ALL_LABELS; do
  [ -z "$lbl" ] && continue
  if ! grep -Fxq -- "$lbl" <<< "$EXISTING_LABELS"; then
    echo "Creating label: $lbl"
    gh api -X POST "repos/$FULL_REPO/labels" \
      -f name="$lbl" \
      -f color="$DEFAULT_LABEL_COLOR" >/dev/null || true
    EXISTING_LABELS=$(printf "%s\n%s\n" "$EXISTING_LABELS" "$lbl" | sort -u)
  else
    echo "Label exists: $lbl"
  fi
done
unset IFS

# ---- Cache existing issue titles to skip duplicates ----
EXISTING_TITLES=$(
  gh issue list --state all --limit 1000 --json title --jq '.[].title' \
  | sort -u
)

echo "== Creating issues =="
LEN=$(jq '.issues | length' "$ISSUES_JSON")
i=0
while [ "$i" -lt "$LEN" ]; do
  TITLE=$(jq -r ".issues[$i].title" "$ISSUES_JSON")
  BODY=$(jq -r ".issues[$i].body"  "$ISSUES_JSON")
  MILESTONE=$(jq -r ".issues[$i].milestone // empty" "$ISSUES_JSON")

  # Gather labels for this issue (newline list)
  ISSUE_LABELS=$(
    jq -r ".issues[$i].labels[]? // empty" "$ISSUES_JSON"
  )

  if grep -Fxq -- "$TITLE" <<< "$EXISTING_TITLES"; then
    echo "Skip (exists): $TITLE"
    i=$((i+1))
    continue
  fi

  echo "Creating: $TITLE"
  # Build args array safely
  ARGS=(issue create --title "$TITLE" --body "$BODY")
  IFS=$'\n'
  for lbl in $ISSUE_LABELS; do
    [ -n "$lbl" ] && ARGS+=(--label "$lbl")
  done
  unset IFS
  [ -n "$MILESTONE" ] && ARGS+=(--milestone "$MILESTONE")

  gh "${ARGS[@]}" >/dev/null

  # Append to existing titles cache
  EXISTING_TITLES=$(printf "%s\n%s\n" "$EXISTING_TITLES" "$TITLE" | sort -u)

  i=$((i+1))
done

echo "Done."
