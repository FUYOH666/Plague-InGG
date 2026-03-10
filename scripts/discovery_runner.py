#!/usr/bin/env python3
"""Discovery runner: agent searches web/GitHub for improvement ideas, appends to evolution-log."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))

DISCOVERY_MESSAGE = (
    "Найди в интернете и на GitHub идеи для улучшения self-improving AI agent. "
    "Используй web_search, github_search_repos, github_search_code. "
    "Добавь 1–3 пункта в evolution_log (append) в секцию «Что изменить». "
    "Только релевантные, конкретные идеи. Пиши по AGENT_ROADMAP."
)


def _check_llm_available(router) -> bool:
    """Verify at least one LLM provider is reachable."""
    try:
        router.chat(
            [{"role": "user", "content": "ok"}],
            tools=None,
            max_tokens=2,
        )
        return True
    except Exception:
        return False


def main() -> None:
    from router import ModelRouter
    from loop import run_loop
    from llm import LLMError

    system_prompt_path = PROJECT_ROOT / "seed" / "prompts" / "ENTRY.md"
    system_prompt = system_prompt_path.read_text(encoding="utf-8").strip() if system_prompt_path.exists() else ""

    router = ModelRouter()
    try:
        if not _check_llm_available(router):
            print("Discovery: LLM unavailable (TailScale/LLM endpoints). Skipping.", file=sys.stderr)
            sys.exit(0)

        print("Discovery: searching web/GitHub for improvement ideas...", file=sys.stderr)
        result = run_loop(
            router=router,
            system_prompt=system_prompt,
            user_message=DISCOVERY_MESSAGE,
            max_rounds=int(os.getenv("MAX_ROUNDS", "20")),
            verbose=True,
        )
        print(f"\n--- Discovery result ---\n{result[:2000]}", file=sys.stderr)
    except LLMError as e:
        print(f"Discovery: LLM error — {e}. Skipping.", file=sys.stderr)
        sys.exit(0)
    finally:
        router.close()


if __name__ == "__main__":
    main()
