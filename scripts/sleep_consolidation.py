#!/usr/bin/env python3
"""Sleep-Time Consolidation (Blueprint 2.2): episodic → semantic, writes to RAG knowledge.
Run via cron (e.g. every 6h) or after daily_reflection."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

SLEEP_INPUT_MAX_CHARS = 12000  # last N chars from session + evolution


def main() -> int:
    memory_dir = PROJECT_ROOT / "data" / "memory"
    session_path = memory_dir / "session-history.md"
    evolution_path = memory_dir / "evolution-log.md"

    session_text = session_path.read_text(encoding="utf-8") if session_path.exists() else ""
    evolution_text = evolution_path.read_text(encoding="utf-8") if evolution_path.exists() else ""

    combined = ""
    if session_text:
        combined += "## session-history\n\n" + session_text[-6000:]
    if evolution_text:
        combined += "\n\n## evolution-log\n\n" + evolution_text[-6000:]

    combined = combined[:SLEEP_INPUT_MAX_CHARS]
    if len(combined.strip()) < 300:
        print("Not enough data for consolidation (min 300 chars)")
        return 0

    from memory_utils import filter_memory_by_salience

    filtered = filter_memory_by_salience(combined, max_chars=SLEEP_INPUT_MAX_CHARS)

    from router import ModelRouter

    prompt = (
        "Извлеки 3–5 ключевых фактов, уроков или паттернов для долговременной памяти агента. "
        "Кратко, по одному предложению на пункт. Только конкретное, без общих фраз.\n\n"
        "--- input ---\n"
        f"{filtered}"
    )

    router = ModelRouter()
    try:
        response = router.chat(
            [
                {"role": "system", "content": "Ты извлекаешь факты для долговременной памяти. Список, кратко."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
            temperature=0.2,
            task="default",
        )
        content = (response.content or "").strip()
        if not content:
            print("No content from LLM")
            return 1

        from rag import rag_index_text

        result = rag_index_text(content, metadata={"source": "sleep"})
        if result.startswith("OK"):
            print(result)
            print("--- extracted ---")
            print(content[:600] + ("..." if len(content) > 600 else ""))
            return 0
        print(result)
        return 1
    finally:
        router.close()


if __name__ == "__main__":
    sys.exit(main())
