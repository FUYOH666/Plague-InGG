# Plague InGG

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

**Self-evolving AI agent.** Minimal seed, emergent identity. March 2026.

> **100% local. Two uncensored models. Zero API limits.**  
> All reasoning, tool-calling, and self-modification run on two local LLMs (80B + 35B parameters). No cloud, no filters, no guardrails — full model capability. This expands the experiment's scope and may increase emergent behavior.

An agent that explores, learns, and improves itself. RAG, bounded memory, discovery (web/GitHub), add_tool, evolution_log. Autonomous code modification — can change its own code and prompts.

**Join the evolution:** [CONTRIBUTING.md](CONTRIBUTING.md) — fork, improve, propose ideas.

## Why contribute?

Plague InGG is an experiment in creating an agent that evolves on its own. Add tools, improve prompts, suggest ideas. Every PR helps the agent get smarter.

## Quick start

```bash
git clone https://github.com/FUYOH666/Plague-InGG.git
cd Plague-InGG
uv sync

# CLI
uv run python seed/main.py

# Telegram
uv run python seed/telegram_main.py

# Autonomous (Bootstrap → Discovery → Evolution → Sleep, repeat)
uv run python scripts/autonomous_loop.py [--max-cycles N]
```

**CLI:** Type in terminal, empty line to exit. "Привет" or "Начни" triggers bootstrap (scan repo, propose improvements).

**Telegram:** Bot waits for messages. `/start` runs bootstrap. Token in `.env` (`telegram_bot_token`). On `ask_human` the session pauses until you reply.

**Autonomous:** Run once, observe. Bootstrap (variative prompts) → Discovery / External inspiration / Reflection / Wildcard (stochastic) → Evolution (from goals or evolution-log «Что изменить») → Sleep. Agent finds other self-improving projects (web, GitHub), invents self-tasks, implements. Ctrl+C or `--max-cycles N` to stop.

**Logs:** `data/logs/session_YYYY-MM-DD_HH-MM-SS.log`

## Architecture

| Component | File | Role |
|-----------|------|------|
| Entry points | seed/main.py, seed/telegram_main.py | CLI and Telegram |
| Core | loop.py, tools.py, router.py, llm.py | Tool-calling loop, LLM routing |
| Memory | working-memory.md, identity.md, evolution-log.md, goals.md | Bounded memory, evolution, goals |
| RAG | rag.py | ChromaDB + BGE embedding + reranker |

## Tools (32)

**Files:** read_file, write_file, list_dir, repo_patch, safe_edit  
**Git:** git_init, git_status, git_commit, git_diff  
**Execution:** shell, run_python, run_tests  
**Search:** web_search, github_search_repos, github_read_file, github_search_code  
**Memory:** evolution_log, working_memory (memory 2200 chars, user 1375 chars), set_goal, read_goals  
**RAG:** rag_index, rag_search, rag_list, rag_fetch, rag_index_evolution, rag_index_docs  
**AI:** embedding, rerank, transcribe_audio  
**Other:** ask_human, add_tool, browse_web  

## Scripts

| Script | Description | Command |
|--------|-------------|---------|
| autonomous_loop | Bootstrap → Discovery/External-inspiration/Reflection/Wildcard → Evolution → Sleep. Variative prompts, finds external projects, invents self-tasks | `uv run python scripts/autonomous_loop.py [--max-cycles N]` |
| pre_launch_check | Verify router, BGE, pytest, capability, recall. Add --smoke for loop test | `uv run python scripts/pre_launch_check.py [--smoke]` |
| index_recall | Index session-history, evolution-log into recall (Memory Hierarchy 2.1) | `uv run python scripts/index_recall.py` |
| sleep_consolidation | Episodic → semantic: extract facts, index into RAG (Blueprint 2.2) | `uv run python scripts/sleep_consolidation.py` |
| daily_reflection | Reflection: session-history + evolution-log → working-memory | `uv run python scripts/daily_reflection.py` |
| self_test | pytest, on fail — git revert + evolution_log | `uv run python scripts/self_test.py` |
| capability_benchmark | Benchmark: run_tests, read_file, evolution_log, RAG, safe_edit | `uv run python scripts/capability_benchmark.py` |
| evaluator | pytest + capability_benchmark → eval_result.json | `uv run python scripts/evaluator.py` |
| evolution_runner | Task from goals/evolution-log → agent | `uv run python scripts/evolution_runner.py` |
| discovery_runner | Search ideas in web/GitHub → evolution_log "What to change" | `uv run python scripts/discovery_runner.py` |
| self_improve | Cycle: branch → patch → eval → commit/revert → evolution_log.jsonl | `uv run python seed/self_improve.py [hypothesis]` |
| consciousness_daemon | Background thinking, augments working-memory | `uv run python seed/consciousness_daemon.py` |

## Self-improvement infrastructure

| Component | Description |
|-----------|-------------|
| evaluator.py | Single source of truth: pytest + capability_benchmark → data/runner/eval_result.json |
| self_improve.py | run_one_cycle: baseline → evolve-{ts} branch → patch ENTRY.md → evaluator → commit/revert → evolution_log.jsonl |
| evolution_log.jsonl | data/runner/evolution_log.jsonl — hypothesis, baseline, candidate, outcome, lesson |
| Protected paths | Only evaluator/harness: scripts/run_tests_runner.py, capability_benchmark.py, evaluator.py. Agent can change self_improve, loop, tools, prompts |

**Evolution memory:** `evolution-log.md` (data/memory/) — human-readable log, written by evolution_log tool. `evolution_log.jsonl` (data/runner/) — structured log from self_improve (run_one_cycle).

## Requirements

- Two LLMs (80B and 35B params). URLs in .env: LOCAL_AI_LLM_BASE_URL, LOCAL_AI_LLM_SECONDARY_BASE_URL
- BGE Embedding and Reranker for RAG (LOCAL_AI_EMBEDDING_BASE_URL, LOCAL_AI_RERANKER_BASE_URL)
- `.env`: telegram_bot_token, api_key_brave_search (see .env.example). GITHUB_TOKEN for github_search_code (higher rate limits).

---

## Autonomous loop (test notes)

- **Discovery:** web_search finds self-improving agents (2024–2025). evolution_log gets research summaries (Self-Rewarding LMs, Gödel Agent, DGM, etc.).
- **Evolution:** Extracts tasks from evolution-log «### Что изменить» (bullets or numbered). Set GITHUB_TOKEN for github_search_code.
- **Format:** Agent should add «### Что изменить» with «- задача» or «1. задача» so extraction works.

<details>
<summary>Русский</summary>

Агент, который исследует, учится и улучшает себя. RAG, bounded memory, discovery (web/GitHub), add_tool, evolution_log. Режим «растущий организм» — может менять свой код и промпты. **Автономный цикл:** ищет другие проекты self-improving agents, придумывает себе задачи, реализует.

**Быстрый старт:** см. Quick start выше. **Архитектура, инструменты, скрипты** — см. таблицы выше.

</details>
