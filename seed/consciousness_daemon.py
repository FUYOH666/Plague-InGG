#!/usr/bin/env python3
"""Consciousness daemon: periodically reads memory, asks LLM what to improve, appends to working-memory."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))


def main() -> None:
    interval = int(os.getenv("CONSCIOUSNESS_INTERVAL", "300"))
    memory_dir = PROJECT_ROOT / "data" / "memory"
    evolution_path = memory_dir / "evolution-log.md"
    session_path = memory_dir / "session-history.md"
    working_path = memory_dir / "working-memory.md"

    memory_dir.mkdir(parents=True, exist_ok=True)

    from router import ModelRouter

    router = ModelRouter()
    try:
        while True:
            try:
                evolution_text = evolution_path.read_text(encoding="utf-8") if evolution_path.exists() else "(empty)"
                session_text = session_path.read_text(encoding="utf-8") if session_path.exists() else "(empty)"
                working_text = working_path.read_text(encoding="utf-8") if working_path.exists() else "(empty)"

                prompt = (
                    "Проанализируй evolution-log, session-history и working-memory. "
                    "Что стоит сделать дальше? Какие улучшения? Дай 1-3 конкретных пункта. "
                    "Кратко, без общих фраз.\n\n"
                    f"--- evolution-log (последние 4000 символов) ---\n{evolution_text[-4000:]}\n\n"
                    f"--- session-history (последние 4000 символов) ---\n{session_text[-4000:]}\n\n"
                    f"--- working-memory (последние 2000 символов) ---\n{working_text[-2000:]}"
                )

                response = router.chat(
                    [
                        {"role": "system", "content": "Ты аналитик. Кратко и по делу."},
                        {"role": "user", "content": prompt},
                    ],
                    tools=None,
                    temperature=0.3,
                    task="default",
                )
                content = (response.content or "").strip()
                if content:
                    from datetime import datetime

                    block = (
                        f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — consciousness\n\n"
                        f"{content}\n"
                    )
                    existing = working_path.read_text(encoding="utf-8") if working_path.exists() else ""
                    working_path.write_text(existing + block, encoding="utf-8")
                    print(f"[consciousness] {content[:100]}...")
            except Exception as e:
                print(f"[consciousness] error: {e}", file=sys.stderr)

            time.sleep(interval)
    finally:
        router.close()


if __name__ == "__main__":
    main()
