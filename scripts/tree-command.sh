#!/bin/bash
# tree-command.sh — Generate a full directory tree snapshot (excluding common junk dirs).
#
# Place at: tools/tree-command.sh
# Run from the repo root.
#
# What this does:
#   - Uses `tree` to recursively list all files and directories.
#   - Includes hidden files (`-a`).
#   - Excludes common virtualenv, cache, build, and download/temp directories.
#   - Writes the output to tree_full.txt at the repo root.
#
# Prereqs:
#   - `tree` command installed (on macOS: brew install tree; on Ubuntu/Debian: apt-get install tree).
#
# Common examples:
#   ./tools/tree-command.sh
#       # Write filtered tree listing to tree_full.txt
#
#   cat tree_full.txt
#       # View the snapshot after generation
#
# Notes:
#   - Adjust the exclusion regex as needed for your repo.
#   - Output overwrites tree_full.txt on each run.
#

tree -a -I '.git|.venv|venv|node_modules|__pycache__|.mypy_cache|.pytest_cache|.next|.expo|dist|build|.cache|downloads|tmp|data/files' > tree_full.txt
