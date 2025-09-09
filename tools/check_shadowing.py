#!/usr/bin/env python3
"""
check_shadowing.py — Detect files in your repo that shadow Python stdlib modules.

Place at: tools/check_shadowing.py
Run from the repo root (folder that contains app/).

What this does:
  - Scans for common stdlib module names (e.g., json, logging, asyncio) that may be
    accidentally shadowed by files in your project (e.g., tools/json.py).
  - Uses importlib.util.find_spec() to see where Python would import each module from.
  - Flags offenders if the resolved path lives under your project root, or if a file
    named "<module>.py" exists at the project root.

Why it matters:
  - Shadowing stdlib modules can lead to confusing import errors and runtime bugs
    (e.g., "AttributeError: module 'json' has no attribute 'loads'").

Exit codes:
  - 0  => No shadowing detected.
  - 1  => One or more offenders detected (paths printed).

Common examples:
  python tools/check_shadowing.py
      # Prints "No stdlib shadowing detected." or lists offenders, then exits accordingly.

Notes:
  - The SUSPECTS list is intentionally conservative. Add more module names if needed.
  - This script assumes your repo structure is <repo>/{app,tools,...}; it marks the
    parent of tools/ as the project root.
"""
from pathlib import Path
import importlib.util
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUSPECTS = [
    "html",
    "json",
    "logging",
    "asyncio",
    "email",
    "types",
    "typing",
    "re",
    "pathlib",
    "dataclasses",
]


def main():
    offenders = []
    for name in SUSPECTS:
        try:
            spec = importlib.util.find_spec(name)
        except Exception:
            spec = None
        origin = getattr(spec, "origin", None) if spec else None
        if isinstance(origin, str):
            p = Path(origin).resolve()
            if str(p).startswith(str(PROJECT_ROOT)):
                offenders.append((name, str(p)))
        f = PROJECT_ROOT / f"{name}.py"
        if f.exists():
            offenders.append((name, str(f.resolve())))
    if offenders:
        print("Stdlib shadowing detected:")
        for name, path in offenders:
            print(f"  - {name}: {path}")
        sys.exit(1)
    print("No stdlib shadowing detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
