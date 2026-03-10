#!/usr/bin/env python3
"""Daily reflection: read session-history and evolution-log, ask LLM what to improve, append to working-memory."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))


def main() -> None:
    from router import ModelRouter

    memory_dir = PROJECT_ROOT / "data" / "memory"
    session_path = memory_dir / "session-history.md"
    evolution_path = memory_dir / "evolution-log.md"
    working_path = memory_dir / "working-memory.md"

    memory_dir.mkdir(parents=True, exist_ok=True)

    session_text = session_path.read_text(encoding="utf-8") if session_path.exists() else "(empty)"
    evolution_text = evolution_path.read_text(encoding="utf-8") if evolution_path.exists() else "(empty)"

    from memory_utils import filter_memory_by_salience
    session_filtered = filter_memory_by_salience(session_text, max_chars=8000)
    evolution_filtered = filter_memory_by_salience(evolution_text, max_chars=8000)

    prompt = (
        "Проанализируй session-history и evolution-log ниже. "
        "Что стоит улучшить в следующих сессиях? Дай краткий список из 3-5 пунктов для working-memory. "
        "Только конкретные действия, без общих фраз.\n\n"
        "--- session-history ---\n"
        f"{session_filtered}\n\n"
        "--- evolution-log ---\n"
        f"{evolution_filtered}"
    )

    router = ModelRouter()
    try:
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
        if not content:
            print("No content from LLM")
            sys.exit(0)

        from datetime import datetime
        block = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')} — daily reflection\n\n{content}\n"
        existing = working_path.read_text(encoding="utf-8") if working_path.exists() else ""
        working_path.write_text(existing + block, encoding="utf-8")
        print("OK: appended to working-memory.md")
        print(content[:500])
    finally:
        router.close()


if __name__ == "__main__":
    main()
