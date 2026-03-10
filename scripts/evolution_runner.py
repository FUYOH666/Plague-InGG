#!/usr/bin/env python3
"""Evolution runner: extract first evolution task from goals or evolution-log, run agent with it."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))


def _extract_task_from_goals() -> str | None:
    """Extract first evolution task from goals.md (skip 'test goal')."""
    goals_path = PROJECT_ROOT / "data" / "memory" / "goals.md"
    if not goals_path.exists():
        return None
    text = goals_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        m = re.match(r"^##\s+\d{4}-\d{2}-\d{2}\s+\|\s+(.+)$", line.strip())
        if m:
            task = m.group(1).strip()
            if task and "test goal" not in task.lower():
                return task
    return None


def _extract_task_from_evolution_log() -> str | None:
    """Extract first task from 'Что изменить' in evolution-log.
    Accepts '### Что изменить' or '### X Что изменить'. Accepts '- ' or '1. ' items."""
    evo_path = PROJECT_ROOT / "data" / "memory" / "evolution-log.md"
    if not evo_path.exists():
        return None
    text = evo_path.read_text(encoding="utf-8")
    in_section = False
    for line in text.splitlines():
        if "Что изменить" in line and line.strip().startswith("###"):
            in_section = True
            continue
        if in_section:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("##") or stripped.startswith("###"):
                break
            if stripped.startswith("- "):
                task = stripped[2:].strip()
                if task and len(task) > 5:
                    return task
            elif re.match(r"^\d+\.\s+", stripped):
                task = re.sub(r"^\d+\.\s+\*\*", "", stripped).replace("**", "").strip()
                if task and len(task) > 5:
                    return task
    return None


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
    task = _extract_task_from_goals() or _extract_task_from_evolution_log()
    if not task:
        print("No evolution task found in goals.md or evolution-log.", file=sys.stderr)
        sys.exit(0)

    message = (
        f"{task} По AGENT_ROADMAP. Пиши код, запускай тесты, коммить."
    )
    print(f"Evolution task: {task}", file=sys.stderr)
    print(f"Message: {message[:80]}...", file=sys.stderr)

    from router import ModelRouter
    from loop import run_loop
    from llm import LLMError

    system_prompt_path = PROJECT_ROOT / "seed" / "prompts" / "ENTRY.md"
    system_prompt = system_prompt_path.read_text(encoding="utf-8").strip() if system_prompt_path.exists() else ""

    router = ModelRouter()
    try:
        if not _check_llm_available(router):
            print("Evolution: LLM unavailable (TailScale/LLM endpoints). Skipping.", file=sys.stderr)
            sys.exit(0)
        result = run_loop(
            router=router,
            system_prompt=system_prompt,
            user_message=message,
            max_rounds=int(os.getenv("MAX_ROUNDS", "30")),
            verbose=True,
        )
        print(f"\n--- Result ---\n{result[:2000]}", file=sys.stderr)
    except LLMError as e:
        print(f"Evolution: LLM error — {e}. Skipping.", file=sys.stderr)
        sys.exit(0)
    finally:
        router.close()


if __name__ == "__main__":
    main()
