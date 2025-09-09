#!/usr/bin/env python3
"""
cleanup.py — Utility to remove generated/temporary files from your repo.

Place at: tools/cleanup.py
Run from the repo root (folder that contains app/).

What this does:
  - Scans for common build artifacts, caches, and temporary files that accumulate
    during development and testing.
  - Removes them to keep your working tree tidy and Git status clean.

Default cleanup targets:
  - __pycache__/ directories
  - *.pyc / *.pyo compiled Python files
  - .pytest_cache/ test cache
  - .mypy_cache/ type checker cache
  - .ruff_cache/ linter cache
  - .coverage, coverage.xml, htmlcov/ coverage reports
  - dist/, build/, *.egg-info/ packaging outputs
  - dev.db (default SQLite DB) unless DATABASE_URL is configured

Exit codes:
  - 0  => Cleanup ran successfully (files may or may not have been removed).
  - 1  => Error occurred (permissions, unexpected failure).

Common examples:
  python tools/cleanup.py
      # Remove all standard cache/temporary files

  python tools/cleanup.py --dry-run
      # Show what would be removed, but don’t delete anything

Notes:
  - Safe to run repeatedly.
  - Extend the TARGETS list if your project creates other disposable files.
"""
from pathlib import Path
import sys
import shutil
import argparse

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TARGETS = [
    "**/__pycache__",
    "**/*.pyc",
    "**/*.pyo",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "coverage.xml",
    "htmlcov",
    "dist",
    "build",
    "*.egg-info",
    "dev.db",
]


def cleanup(dry_run: bool = False, verbose: bool = False) -> int:
    removed = 0
    for pattern in TARGETS:
        for path in PROJECT_ROOT.glob(pattern):
            try:
                if path.is_dir():
                    if dry_run:
                        print(f"[DRY RUN] Would remove dir: {path}")
                    else:
                        shutil.rmtree(path, ignore_errors=True)
                        if verbose:
                            print(f"Removed dir: {path}")
                    removed += 1
                elif path.exists():
                    if dry_run:
                        print(f"[DRY RUN] Would remove file: {path}")
                    else:
                        path.unlink(missing_ok=True)
                        if verbose:
                            print(f"Removed file: {path}")
                    removed += 1
            except Exception as e:
                print(f"Error removing {path}: {e}", file=sys.stderr)
                return 1
    if verbose or dry_run:
        print(f"Cleanup complete. {removed} items {'would be' if dry_run else 'were'} removed.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Remove caches and temporary build/test files.")
    ap.add_argument("--dry-run", action="store_true", help="Show what would be removed, but don’t delete.")
    ap.add_argument("-v", "--verbose", action="store_true", help="Verbose output.")
    args = ap.parse_args()

    return cleanup(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
