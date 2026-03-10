#!/usr/bin/env python3
"""Index session-history and evolution-log into recall collection (Blueprint 2.1).
Run after session or via cron."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "seed"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from rag import recall_index


def main() -> int:
    memory_dir = PROJECT_ROOT / "data" / "memory"
    evolution_path = memory_dir / "evolution-log.md"
    session_path = memory_dir / "session-history.md"

    indexed = 0
    for path in [evolution_path, session_path]:
        if path.exists():
            rel = str(path.relative_to(PROJECT_ROOT))
            result = recall_index(rel)
            print(result)
            if result.startswith("OK"):
                indexed += 1
        else:
            print(f"Skip (not found): {path.name}")

    if indexed == 0:
        print("No files indexed. Ensure evolution-log.md or session-history.md exist.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
