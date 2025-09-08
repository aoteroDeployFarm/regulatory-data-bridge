#!/usr/bin/env python3
from pathlib import Path
import importlib.util
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SUSPECTS = ["html","json","logging","asyncio","email","types","typing","re","pathlib","dataclasses"]

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
