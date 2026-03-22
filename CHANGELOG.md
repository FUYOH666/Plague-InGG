# Changelog

## [Unreleased]

### Изменено

- **seed/goals.md** — раздел «Мандат эксперимента»: инициатива, выбор направления, цикл `self_improve`, границы и тон для самоэволюции
- **Идентичность / UX** — бренд **Plague-InGG** вместо «Seed of Attention» / «семя внимания»: [seed/identity.md](seed/identity.md), REPL и docstring [kernel/core.py](kernel/core.py), [main.py](main.py); нейтральная строка `thinking...`
- **Конфиг OpenRouter + RAG** — README / `.env.example`: явно `openai/gpt-5.4-nano`, предупреждение про `LLM_BASE_URL=localhost` при `openrouter`; `resolve_raw_base_url` игнорирует локальный `LLM_BASE_URL` в режиме OpenRouter с логом

### Исправлено

- **self_improve** — корректный `git merge --no-ff <ветка>` и `git branch -D <ветка>`; имя ветки сохраняется в `evolution/.active_evolve_branch` (в `.gitignore`); проверка текущей ветки для `test`/`commit`; pytest через `sys.executable -m pytest`; сообщения об ошибках git; опциональный параметр `branch`; тесты `tests/test_self_improve.py`

### Добавлено

- **OpenRouter** — `LLM_PROVIDER=openrouter`, база `https://openrouter.ai/api/v1`, модель по умолчанию `openai/gpt-5.4-nano`, опциональные `OPENROUTER_HTTP_REFERER` / `OPENROUTER_APP_TITLE`
- **llm_settings** — разрешение URL/заголовков и `post_chat_completion`; тесты `tests/test_llm_settings.py`
- **RAG_STRICT** / **REFLECTION_STRICT** — опциональный проброс ошибок вместо только логирования
- **Удалённый LLM-сервис** — приоритетный базовый URL через `LOCAL_AI_LLM_BASE_URL` (OpenAI-compatible /v1)
- **Brave Search** — веб-поиск, настройка через `BRAVE_API_KEY`
- **memory_manager** — инструмент: status, summarize, archive, hierarchy; персистентность в `memory/archive.json`
- **RAG-память** (`memory/rag.py`) — семантический поиск по памяти через Embedding API (BGE-M3, порт 9001)
- **Цикл рефлексии** — после каждого ответа LLM суммаризирует обмен и пишет в память
- **Smoke-тесты** (`tests/test_tools_smoke.py`) — проверка загрузки и execute для всех инструментов
- **Валидация create_tool** — smoke test после создания, откат при ошибке
- **Скрипт `run`** — запуск через `./run` без `python`
- **Индикация** — "thinking...", "→ tool..." при работе
- **TOOL_RESULT_MAX_CHARS** — обрезка вывода инструментов перед вставкой в контекст LLM (`kernel/core.py`)
- **SHELL_POLICY** — `deny` (по умолчанию) / `strict` / `off` (`tools/shell.py`)
- **str_replace_file** — точечная замена одной подстроки в файле
- **WRITE_FILE_SHRINK_GUARD** — опциональный отказ при сильном уменьшении существующего файла
- **LLM_LOG_USAGE** — запись `usage` из ответа API в `evolution/llm_usage.jsonl`
- **seed/dao.md** — опциональный протокол намерений в system prompt (заменяет constitution; DAO = редактируемый документ, не блокчейн)

### Изменено

- **DAO** — `seed/constitution.md` заменён на `seed/dao.md` (протокол намерений; без отсылки к Bible/Ouroboros)
- **LLM** — удалён термин Foundry; `LOCAL_AI_LLM_BASE_URL`; `LLM_PROVIDER`: `local` | `openrouter`; модель/таймаут через `LLM_MODEL`, `LLM_TIMEOUT`
- **requirements.txt** — валидный pip-fallback; в README указан приоритет `uv sync`
- **pyproject.toml** — `py-modules` для `llm_settings` (без `[tool.pip]`)
- **kernel** — `logging` для tools/RAG/рефлексии; флаги `RAG_STRICT` / `REFLECTION_STRICT`
- **main.py** — `load_llm_settings`, логирование HTTP-ошибок LLM, `logging.basicConfig` в CLI
- **REPL** — пустая строка не выходит; выход: `exit` / `quit` / `q` / Ctrl+D
- **MEMORY_MAX_CHARS**, **build_system_prompt** (RAG), **.env.example** — как ранее в релизе
- **Репозиторий** — удалён `.pip.conf`; `.gitignore`: `.pytest_cache/`, `.ruff_cache/`, `.pip.conf`, `evolution/llm_usage.jsonl`
- **shell** — политика по умолчанию `deny`; настраиваемые префиксы для `strict`
- **README / .env.example** — документация новых флагов
