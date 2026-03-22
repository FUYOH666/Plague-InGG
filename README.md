# Plague-InGG

**Self-evolving AI agent.** Minimal kernel, RAG, reflection. ~200 lines of immutable core — everything else grows.

> [https://github.com/FUYOH666/Plague-InGG](https://github.com/FUYOH666/Plague-InGG)

## Philosophy

This project is built on one principle: **the simplest possible core that can grow into anything.**

Like attention itself — it has no content, no personality, no fixed goals. It is pure capability: perceive → think → act → remember → evaluate. Everything else — identity, tools, memory, goals — is created by the agent itself.

### Architecture as Metaphor

| Concept | In the Agent | In Consciousness |
|---------|-------------|-----------------|
| **Kernel** (immutable) | `kernel/core.py` — the loop | Attention — pure awareness |
| **Identity** (mutable) | `seed/identity.md` | Ego — self-model |
| **Memory** (mutable) | `memory/stream.md` | Experience stream |
| **Tools** (mutable) | `tools/*.py` | Capabilities, skills |
| **Goals** (mutable) | `seed/goals.md` | Intentions |
| **Evolution log** | `evolution/log.jsonl` | Growth awareness |

The agent **can modify everything except the kernel**. This is the DNA constraint: proteins mutate freely, but the genetic code is conserved.

## Quick Start

```bash
git clone https://github.com/FUYOH666/Plague-InGG.git
# или SSH: git clone git@github.com:FUYOH666/Plague-InGG.git
cd Plague-InGG
cp .env.example .env  # LLM, Brave API key, Embedding URL
uv sync   # canonical install (see pyproject.toml + uv.lock)
./run
# или: uv run main.py
```

`pip install -r requirements.txt` is a minimal fallback only; prefer **`uv sync`**.

**Проверки:** `uv run pytest` — тесты; опционально `uvx ruff check .` (линт без добавления зависимости в проект).

**Идеи из Ouroboros-подобных систем (без десктоп-стека):** лимит размера результата инструментов в контексте (`TOOL_RESULT_MAX_CHARS`), политика `shell` (`SHELL_POLICY`), защита от случайного усечения файла (`WRITE_FILE_SHRINK_GUARD`), инструмент `str_replace_file`, лог usage в `evolution/llm_usage.jsonl`, опциональный **`seed/dao.md`** — не блокчейн-DAO, а **протокол намерений** (редактируемый документ принципов). См. `.env.example`.

**REPL:** вводи сообщения, пустая строка — пропуск. Выход: `exit`, `quit`, `q` или Ctrl+D.

### MacBook + удалённый LLM-сервис (TailScale)

Для работы с удалённым OpenAI-совместимым LLM (например порт 8005, llama.cpp server):

```bash
# В .env добавьте:
LOCAL_AI_LLM_BASE_URL=http://YOUR_TAILSCALE_HOST:8005/v1
LLM_MODEL=default
```

### OpenRouter + эмбеддинги (типичный стек)

Чат: провайдер [OpenRouter](https://openrouter.ai/) (OpenAI Chat Completions). Рекомендуемая модель: [`openai/gpt-5.4-nano`](https://openrouter.ai/openai/gpt-5.4-nano) (контекст до 400k токенов, см. карточку модели на OpenRouter).

Память (RAG): тот же `.env` — `LOCAL_AI_EMBEDDING_BASE_URL` на ваш **BGE-M3** сервис (OpenAI-compatible, порт **9001**; в коде к base добавляется `/v1/embeddings`).

```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=your-openrouter-api-key   # https://openrouter.ai/keys
LLM_MODEL=openai/gpt-5.4-nano
# Не указывайте LLM_BASE_URL=http://localhost:... при openrouter — иначе запросы уйдут на localhost.
# LLM_BASE_URL по умолчанию https://openrouter.ai/api/v1
LOCAL_AI_EMBEDDING_BASE_URL=http://YOUR_TAILSCALE_HOST:9001
# Опционально для лидерборда OpenRouter:
# OPENROUTER_HTTP_REFERER=https://your-site.example
# OPENROUTER_APP_TITLE=Plague-InGG
```

### Brave Search (доступ в интернет)

Инструмент `brave_search` даёт агенту доступ к веб-поиску. Получите API-ключ на [brave.com/search/api](https://brave.com/search/api/) и добавьте в `.env`:

```bash
BRAVE_API_KEY=your-brave-api-key-here
```

### RAG-память и рефлексия

- **RAG** — семантический поиск по памяти (Embedding API на 9001). `LOCAL_AI_EMBEDDING_BASE_URL` в `.env`. Сбои логируются; `RAG_STRICT=true` прерывает цикл при ошибке индекса/ретрива
- **Рефлексия** — после каждого ответа агент суммаризирует обмен и пишет в память. Отключить: `REFLECTION_ENABLED=false`. `REFLECTION_STRICT=true` — проброс ошибок суммаризации
- **memory_manager** — `action=summarize` для сжатия stream.md в archive.json

## Structure

```
Plague-InGG/
├── kernel/
│   └── core.py          # THE KERNEL. Loop, RAG, reflection.
├── seed/
│   ├── identity.md      # Who am I? (agent writes this)
│   ├── goals.md         # What do I want? (agent writes this)
│   └── dao.md           # Optional DAO protocol (injected if non-empty; not on-chain DAO)
├── tools/
│   ├── remember.py      # Write to memory stream
│   ├── read_file.py     # Read any file
│   ├── write_file.py    # Write any file (except kernel); optional shrink guard
│   ├── str_replace_file.py # One exact substring replace (safer edits)
│   ├── create_tool.py   # ★ Create new tools (+ smoke validation)
│   ├── brave_search.py  # Search the web
│   ├── memory_manager.py # Summarize, archive stream → archive.json
│   ├── shell.py         # Execute commands
│   ├── list_dir.py      # List directory
│   └── self_improve.py  # Branch → mutate → test → keep/revert
├── memory/
│   ├── stream.md        # Agent's memory journal
│   ├── archive.json     # Archived/summarized records
│   ├── rag.py           # RAG: embed, index, retrieve
│   └── vectors.jsonl    # Vector index (gitignored)
├── tests/
│   ├── test_tools_smoke.py
│   └── test_llm_settings.py
├── evolution/
│   ├── log.jsonl        # Structured evolution history (gitignored if local)
│   └── llm_usage.jsonl  # Token usage from API when LLM_LOG_USAGE=1 (gitignored)
├── main.py              # Entry point (LLM adapter)
├── llm_settings.py      # LLM base URL, OpenRouter headers, chat client
├── run                  # ./run to start
└── .env                 # Configuration
```

## Итоги доработок (тезисно)

| Область | Что сделано |
|---------|-------------|
| **LLM** | Удалённый сервис `LOCAL_AI_LLM_BASE_URL` (OpenAI-compatible /v1); опция **OpenRouter** (`LLM_PROVIDER=openrouter`, nano по умолчанию) |
| **Интернет** | Brave Search, `BRAVE_API_KEY` |
| **Память** | `MEMORY_MAX_CHARS`, RAG (Embedding 9001), memory_manager с archive |
| **Рефлексия** | Авто-суммаризация после ответа, `REFLECTION_ENABLED` |
| **Инструменты** | create_tool с smoke-валидацией, memory_manager |
| **Тесты** | `test_tools_smoke.py`, `test_llm_settings.py` |
| **UX** | `./run`, индикация "thinking...", пустая строка не выходит |

## How It Works

### The Kernel (Sacred, Immutable)

`kernel/core.py` does exactly five things:
1. **Discovers tools** — scans `tools/` directory, loads TOOL_SPEC + execute()
2. **Builds context** — assembles identity + goals + memory + tool list into system prompt
3. **Runs the loop** — sends to LLM, parses tool calls, executes, repeats
4. **Parses responses** — extracts `tool` JSON blocks from LLM output
5. **Provides REPL** — terminal interface

Plus: **RAG** (semantic retrieval from memory), **reflection** (auto-summarize after each response), **memory_manager** (summarize/archive).

### Bootstrap Tools (Agent Can Modify/Delete)

| Tool | Role |
|------|------|
| `remember` | Write to memory |
| `read_file` | Read files |
| `write_file` | Write files |
| `create_tool` | ★ Create new tools (+ smoke validation) |
| `brave_search` | Web search |
| `memory_manager` | Summarize/archive stream → archive.json |
| `shell` | Execute commands |
| `list_dir` | List directory |
| `self_improve` | Evolution cycle |

### The Key Insight: create_tool

The agent doesn't start with dozens of hardcoded tools. It starts with a **small bootstrap set** (see `tools/*.py` with `TOOL_SPEC`). One of them — `create_tool` — lets it create *any tool it needs*. Need RAG? The project already ships `memory/rag.py`; the agent can extend via tools as needed.

A tool the agent creates itself is a tool the agent *understands* and can *modify*. A tool you hardcode is a black box to the agent.

### Self-Improvement Cycle

```
1. Agent forms hypothesis: "I need a tool for X"
2. self_improve(action="start") → creates git branch
3. Agent creates/modifies tool using write_file or create_tool
4. self_improve(action="test") → runs pytest
5. Tests pass → self_improve(action="commit") → merged to main
6. Tests fail → self_improve(action="revert") → discarded
7. Evolution logged to evolution/log.jsonl
```

After `action=start`, the active evolve branch name is stored in `evolution/.active_evolve_branch` (one line, local only; gitignored) so `test`, `commit`, and `revert` know which branch to use. You can override it with the optional `branch` parameter. Tests are run with the same Python interpreter as the agent (`python -m pytest` via `sys.executable`).

## Design Principles

1. **Minimal kernel** — 200 lines, does nothing special, enables everything
2. **Agent-created tools** — capabilities grow organically, not by hardcoding
3. **Protected DNA** — kernel/core.py cannot be modified by the agent
4. **Single memory stream** — one markdown file, agent structures it as needed
5. **Fitness over features** — measure improvement, not complexity
6. **Evolution log** — every change recorded with reason and outcome

## Legacy (v1)

| Aspect | v1 (old) | v2 (current) |
|--------|-----------------|----------------------|
| Bootstrap tools | 32 | Small set (`tools/` + `TOOL_SPEC`) |
| Kernel size | ~2000+ lines across files | ~200 lines, one file |
| Memory system | 5 files, bounded, structured | 1 file, agent structures it |
| Self-modification | Complex pipeline | Simple: write_file + git |
| RAG | Built-in ChromaDB | Built-in (memory/rag.py, Embedding API) |
| Philosophy | "Give agent everything" | "Give agent the ability to create anything" |

## License

MIT — because open source is anti-compression.

---

*"The agent is not its tools. It is not its memory. It is the process that uses them."*
