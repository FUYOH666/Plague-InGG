#!/usr/bin/env python3
"""Autonomous evolution loop: Bootstrap → Discovery → Evolution → Sleep → repeat.
Run once, observe. Graceful shutdown on SIGTERM, --max-cycles N.
Variative prompts, reflection-only, wildcard phases for creativity."""

from __future__ import annotations

import argparse
import os
import random
import re
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))

BOOTSTRAP_VARIANTS = (
    "Что тебе интересно прямо сейчас? Изучи репо и выбери одно направление.",
    "Изучи репозиторий: list_dir, read_file AGENT_ROADMAP.md, goals, evolution-log. "
    "Что хочешь сделать? Предложи 1–3 направления.",
    "Ограничение: не используй set_goal в этом цикле. Что бы ты сделала?",
    "Найди в коде что-то, что тебя удивило. Запиши в evolution_log.",
    "Прочитай session-history и evolution-log. Что сделать по-другому в этом цикле?",
    "Что бы ты сделала по умолчанию? Рассмотри второй по приоритету вариант.",
    "Найди на GitHub или в web поиске один проект self-improving agent. Что из него можно взять? Придумай себе задачу и добавь в evolution_log.",
)
DISCOVERY_VARIANTS = (
    "Найди на GitHub другие проекты self-improving / self-evolving AI agents. Изучи 2–3 репо. "
    "Какие идеи оттуда можно взять? Добавь в evolution_log (append) в «Что изменить» — придумай себе 1–3 задачи на основе найденного.",
    "Ищи в интернете: self-improving agents, autonomous coding agents, AI self-modification 2024–2025. "
    "Найди идеи, которых нет в AGENT_ROADMAP. Придумай себе задачу и добавь в evolution_log.",
    "github_search_repos: self-evolving agent, autonomous AI. Прочитай README 2–3 проектов через github_read_file. "
    "Что из их подхода можно взять? Добавь в «Что изменить».",
    "Найди в интернете и на GitHub идеи для улучшения self-improving AI agent. "
    "Используй web_search, github_search_repos, github_search_code. "
    "Добавь 1–3 пункта в evolution_log (append) в секцию «Что изменить». Только релевантные, конкретные идеи.",
)
EXTERNAL_INSPIRATION_MESSAGE = (
    "Твоя задача — придумать себе задачи извне. Найди 2–3 проекта self-improving agents на GitHub, "
    "прочитай их README/документацию. Извлеки 1–2 конкретные идеи. "
    "Добавь в evolution_log и set_goal — это задачи, которые ты сама себе придумала. Пиши по AGENT_ROADMAP."
)
REFLECTION_ONLY_MESSAGE = (
    "Только рефлексия. Прочитай evolution-log, session-history. "
    "Напиши 3 гипотезы, что улучшить. Не делай — только запиши в evolution_log (append)."
)
WILDCARD_VARIANTS = (
    "Ограничение: не используй read_file и list_dir. Сделай что-то, чего ты ещё не делала в этом репо.",
    "Найди в web_search или github_search одну идею, которая противоречит или расширяет AGENT_ROADMAP. Запиши в evolution_log.",
)

_shutdown_requested = False


def _on_sigterm(*_args) -> None:
    global _shutdown_requested
    _shutdown_requested = True


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
    """Extract first task from 'Что изменить' section in evolution-log.
    Accepts '### Что изменить' or '### X Что изменить' (e.g. with emoji).
    Accepts '- ' bullets or '1. ' numbered items."""
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
    try:
        router.chat(
            [{"role": "user", "content": "ok"}],
            tools=None,
            max_tokens=2,
        )
        return True
    except Exception:
        return False


def _log(msg: str, log_path: Path | None = None) -> None:
    print(msg, file=sys.stderr)
    if log_path:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass


def _get_last_cycle_summary(log_path: Path | None, max_chars: int = 500) -> str:
    """Read last cycle summary from autonomous log or session-history for context."""
    if not log_path or not log_path.exists():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8")
        return text[-max_chars:].strip()
    except Exception:
        return ""


def _get_bootstrap_message(cycle: int, prev_summary: str) -> str:
    """Select bootstrap variant, inject previous cycle context when available."""
    variant = BOOTSTRAP_VARIANTS[cycle % len(BOOTSTRAP_VARIANTS)]
    if prev_summary:
        return f"В прошлом цикле: {prev_summary[:400]}... Что хочешь сделать по-другому или продолжить?\n\n{variant}"
    return variant


def _get_discovery_message(cycle: int) -> str:
    """Select discovery variant by cycle."""
    return DISCOVERY_VARIANTS[cycle % len(DISCOVERY_VARIANTS)]


def _run_phase(
    phase: str,
    message: str,
    max_rounds: int,
    router,
    system_prompt: str,
    log_path: Path | None,
    temperature: float = 0.7,
) -> str:
    from loop import run_loop

    _log(f"[{phase}] Running...", log_path)
    try:
        result = run_loop(
            router=router,
            system_prompt=system_prompt,
            user_message=message,
            max_rounds=max_rounds,
            temperature=temperature,
            verbose=True,
        )
        preview = (result or "")[:500]
        _log(f"[{phase}] Result: {preview}...", log_path)
        return result or ""
    except Exception as e:
        _log(f"[{phase}] Error: {e}", log_path)
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous evolution loop")
    parser.add_argument("--max-cycles", type=int, default=0, help="Max cycles (0=infinite)")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _on_sigterm)
    signal.signal(signal.SIGINT, _on_sigterm)

    if os.getenv("AUTONOMOUS_ENABLED", "true").lower() not in ("true", "1", "yes"):
        print("AUTONOMOUS_ENABLED is false. Exiting.", file=sys.stderr)
        return 0

    sleep_minutes = int(os.getenv("AUTONOMOUS_SLEEP_MINUTES", "7"))
    max_rounds_bootstrap = int(os.getenv("AUTONOMOUS_MAX_ROUNDS_BOOTSTRAP", "15"))
    max_rounds_discovery = int(os.getenv("AUTONOMOUS_MAX_ROUNDS_DISCOVERY", "20"))
    max_rounds_evolution = int(os.getenv("AUTONOMOUS_MAX_ROUNDS_EVOLUTION", "30"))
    wildcard_chance = float(os.getenv("AUTONOMOUS_WILDCARD_CHANCE", "0.12"))
    reflection_chance = float(os.getenv("AUTONOMOUS_REFLECTION_CHANCE", "0.20"))
    external_inspiration_chance = float(os.getenv("AUTONOMOUS_EXTERNAL_INSPIRATION_CHANCE", "0.17"))
    temp_creative = float(os.getenv("AUTONOMOUS_TEMP_CREATIVE", "0.75"))
    temp_evolution = float(os.getenv("AUTONOMOUS_TEMP_EVOLUTION", "0.3"))

    logs_dir = PROJECT_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"autonomous_{datetime.now().strftime('%Y-%m-%d')}.log"

    system_prompt_path = PROJECT_ROOT / "seed" / "prompts" / "ENTRY.md"
    system_prompt = (
        system_prompt_path.read_text(encoding="utf-8").strip()
        if system_prompt_path.exists()
        else ""
    )

    from router import ModelRouter
    from llm import LLMError

    router = ModelRouter()
    try:
        if not _check_llm_available(router):
            _log("LLM unavailable. Exiting.", log_path)
            return 1

        _log("Autonomous loop started. Ctrl+C or SIGTERM to stop.", log_path)
        cycle = 0

        while not _shutdown_requested:
            cycle += 1
            if args.max_cycles > 0 and cycle > args.max_cycles:
                _log(f"Reached max-cycles={args.max_cycles}. Stopping.", log_path)
                break

            _log(f"\n=== Cycle {cycle} ===", log_path)

            prev_summary = _get_last_cycle_summary(log_path)

            # Phase 1: Bootstrap (always first)
            bootstrap_msg = _get_bootstrap_message(cycle, prev_summary)
            _run_phase(
                "Bootstrap",
                bootstrap_msg,
                max_rounds_bootstrap,
                router,
                system_prompt,
                log_path,
                temperature=temp_creative,
            )
            if _shutdown_requested:
                break

            # Phase 2: one of Reflection-only, Wildcard, External inspiration, or Discovery
            r = random.random()
            if r < reflection_chance:
                _run_phase(
                    "Reflection-only",
                    REFLECTION_ONLY_MESSAGE,
                    max_rounds_bootstrap,
                    router,
                    system_prompt,
                    log_path,
                    temperature=temp_creative,
                )
                if _shutdown_requested:
                    break
            elif r < reflection_chance + wildcard_chance:
                wildcard_msg = random.choice(WILDCARD_VARIANTS)
                _run_phase(
                    "Wildcard",
                    wildcard_msg,
                    max_rounds_discovery,
                    router,
                    system_prompt,
                    log_path,
                    temperature=temp_creative,
                )
                if _shutdown_requested:
                    break
            elif r < reflection_chance + wildcard_chance + external_inspiration_chance:
                _run_phase(
                    "External-inspiration",
                    EXTERNAL_INSPIRATION_MESSAGE,
                    max_rounds_discovery,
                    router,
                    system_prompt,
                    log_path,
                    temperature=temp_creative,
                )
                if _shutdown_requested:
                    break
            else:
                discovery_msg = _get_discovery_message(cycle)
                _run_phase(
                    "Discovery",
                    discovery_msg,
                    max_rounds_discovery,
                    router,
                    system_prompt,
                    log_path,
                    temperature=temp_creative,
                )
                if _shutdown_requested:
                    break

            # Phase 3: Evolution (70% when task exists)
            task = _extract_task_from_goals() or _extract_task_from_evolution_log()
            if task and random.random() < 0.7:
                evo_message = f"{task} По AGENT_ROADMAP. Пиши код, запускай тесты, коммить."
                _run_phase(
                    "Evolution",
                    evo_message,
                    max_rounds_evolution,
                    router,
                    system_prompt,
                    log_path,
                    temperature=temp_evolution,
                )
            elif task:
                _log("[Evolution] Skipped (stochastic).", log_path)
            else:
                _log("[Evolution] No task in goals or evolution-log. Skipping.", log_path)

            if _shutdown_requested:
                break

            # Phase 4: Sleep
            _log(f"[Sleep] {sleep_minutes} minutes...", log_path)
            for _ in range(sleep_minutes * 60):
                if _shutdown_requested:
                    break
                time.sleep(1)

        _log("Autonomous loop stopped.", log_path)
        return 0
    except LLMError as e:
        _log(f"LLM error: {e}", log_path)
        return 1
    finally:
        router.close()


if __name__ == "__main__":
    sys.exit(main())
