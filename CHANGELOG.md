# Changelog

## [Unreleased]

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

### Изменено

- **LLM** — удалён термин Foundry; приоритетный URL удалённого сервиса: `LOCAL_AI_LLM_BASE_URL`; `LLM_PROVIDER` только `local` или `openrouter`
- **requirements.txt** — убраны недопустимые для pip строки из `[tool.pip]`; добавлена отсылка к `uv sync`
- **pyproject.toml** — удалён `[tool.pip]`; объявлен `py-modules` для `llm_settings`
- **kernel** — ошибки загрузки tools, RAG и рефлексии логируются через `logging` вместо молчаливых `except`
- **main.py** — конфиг LLM через `load_llm_settings`, логирование HTTP-ошибок LLM, `logging.basicConfig` при запуске из CLI
- **REPL** — пустая строка не выходит; выход по `exit`/`quit`/`q` или Ctrl+D
- **MEMORY_MAX_CHARS** — конфигурируемый лимит (по умолчанию 4000)
- **build_system_prompt** — интеграция RAG (релевантные чанки по запросу)
- **LLM** — модель `default`, таймаут через `LLM_TIMEOUT`
- **.env.example** — MEMORY_MAX_CHARS, REFLECTION_ENABLED, LOCAL_AI_EMBEDDING_BASE_URL
