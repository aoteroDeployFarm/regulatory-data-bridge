#!/usr/bin/env bash
# bootstrap.sh — Initialize dev environment, DB index, and start API server.
#
# Place at: tools/bootstrap.sh
# Run from the repo root.
#
# What this does:
#   - Ensures Python virtualenv `.venv` exists (creates if missing).
#   - Activates the venv (supports bash, zsh, fish, fallback).
#   - Installs pip, wheel, and project dependencies (requirements.txt or setup.cfg/pyproject.toml).
#   - Ensures SQLite index for document_versions(change_type, fetched_at).
#   - Launches uvicorn with hot reload on port 8000.
#
# Prereqs:
#   - Python 3 installed
#   - sqlite3 CLI installed
#   - uvicorn available (via pip install uvicorn[standard])
#
# Common examples:
#   ./tools/bootstrap.sh
#       # Bootstrap environment and start dev server
#
# Notes:
#   - Run once per fresh checkout to initialize environment and DB.
#   - Safe to re-run; venv and DB index creation are idempotent.
#
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Create venv if missing
if [ ! -d ".venv" ]; then
  echo "Creating .venv..."
  python3 -m venv .venv
fi

# Detect shell for activation
if [ -n "${BASH_VERSION:-}" ] || [ -n "${ZSH_VERSION:-}" ]; then
  # bash/zsh
  # shellcheck source=/dev/null
  source .venv/bin/activate
elif [ -n "${FISH_VERSION:-}" ]; then
  # fish
  # shellcheck disable=SC1091
  source .venv/bin/activate.fish
else
  # fallback
  # shellcheck source=/dev/null
  source .venv/bin/activate || true
fi

python -m pip install -U pip wheel
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
elif [ -f setup.cfg ] || [ -f pyproject.toml ]; then
  pip install -e .
fi

sqlite3 dev.db "CREATE INDEX IF NOT EXISTS ix_doc_versions_change_time ON document_versions(change_type, fetched_at DESC);"

echo "Env ready. Starting API..."
uvicorn app.main:app --reload --port 8000
