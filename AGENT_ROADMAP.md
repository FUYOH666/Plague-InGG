# Ekaterina v2/v3 — Дорожная карта самосоздающегося агента

> Как собрать ИИ-агента, который достроит себя сам.
> Дата: 2026-03-09

**Текущее состояние (v3):** Компрессия контекста, RAG (ChromaDB), bounded memory, safe_edit, ask_human, set_goal/read_goals, add_tool, browse_web, rag_index_evolution, rag_list, rag_fetch, runner как источник истины, capability-gate. 32 инструмента. **Инфраструктура самоулучшения:** evaluator, self_improve (run_one_cycle), evolution_log.jsonl, protected paths. **Blueprint Фаза 1 (выполнена):** Capability zones (Red/Orange/Yellow/Green), Metacognitive monitor, Forgetting curves. **Следующий этап — Фаза 2.1:** Memory Hierarchy (Letta-style): Core (identity + working-memory prefix) → Recall (session-history, evolution-log в ChromaDB) → Archival (knowledge). См. [README.md](README.md).

---

## Философия: Зерно → Дерево

Мы не пишем готовый продукт. Мы создаём **минимальное зерно** (seed) — ~500 строк Python, которое умеет:
1. Подключаться к двум LLM (80B + 35B параметров)
2. Читать/писать файлы
3. Выполнять bash-команды
4. Коммитить изменения в git
5. Запускать тесты

Всё остальное — Telegram-бот, RAG, consciousness, plugin-система — агент напишет сам, получая задачи через простой интерфейс.

Это не теория. Паттерн SICA (Self-Improving Coding Agent, 2025) показал рост производительности с 17% до 53% при самомодификации. AlphaEvolve от DeepMind и Darwin-Gödel Machine доказали, что эволюция из минимального зерна работает.

---

## Наша инфраструктура

```
┌─────────────────────────────────────────────────────────────────┐
│  Оркестратор (ваш компьютер)                                   │
│  Роль: ОРКЕСТРАТОР                                              │
│  - Запускает seed / Plague InGG                                 │
│  - Никакого локального AI                                       │
│  - Все запросы к LLM/Embedding (URL в .env)                     │
└──────────┬──────────────────────────┬───────────────────────────┘
           │                          │
           ▼                          ▼
┌──────────────────────────┐ ┌────────────────────────────────────┐
│ LLM #1 (80B)             │ │ LLM #2 (35B)                        │
│ YOUR_LLM_HOST:1234       │ │ YOUR_LLM_SECONDARY_HOST:8005         │
│                          │ │                                    │
│ Контекст: 203K           │ │ Контекст: 120K × 2 слота           │
│ Слоты: 1                 │ │ Слоты: 2 (параллельные)            │
│                          │ │                                    │
│ BGE Embedding :9001      │ │ ASR :8001                          │
│ BGE Reranker  :9002      │ │                                    │
└──────────────────────────┘ └────────────────────────────────────┘
```

### Два мозга — разные роли

| Роль | LLM (80B) | LLM (35B × 2) |
|------|-----------|---------------|
| Архитектор | ✅ Планирует, проектирует | — |
| Код | ✅ Пишет сложный код | ✅ Пишет простой код |
| Ревьюер | ✅ Проверяет код 35B | — |
| Параллельность | ❌ 1 слот | ✅ 2 слота одновременно |
| Tool calling | ✅ Основной | ✅ Когда 80B занят |
| Рефлексия | ✅ Глубокая | ✅ Быстрая |
| Контекст | 203K токенов | 120K на слот |

---

## Инфраструктура самоулучшения (реализовано)

**Self-modifying ≠ self-improving.** Агент может менять себя (write_file, add_tool), но без внешнего контура он блуждает. Нужен цикл: fitness → sandbox → independent verification → accept/reject.

### Компоненты

| Компонент | Файл | Роль |
|-----------|------|------|
| **Evaluator** | `scripts/evaluator.py` | Единая точка: pytest + capability_benchmark → `eval_result.json`. LLM не источник истины о тестах. |
| **self_improve** | `seed/self_improve.py` | Цикл: baseline → `evolve-{ts}` branch → patch (только ENTRY.md) → evaluator → commit или revert → `evolution_log.jsonl` |
| **evolution_log.jsonl** | `data/runner/evolution_log.jsonl` | Архив попыток: hypothesis, patch_id, baseline, candidate, outcome, lesson |
| **Policy** | `seed/tools.py` | Protected paths: evaluator, run_tests_runner, capability_benchmark, seed/self_improve.py. Агент не может их менять. |

### Поток

```
propose_change → create_branch → apply_patch → run_evaluator → compare_baseline → commit_or_revert → write_lesson
```

### Ограничения (24h scope)

- Одна зона: `seed/prompts/ENTRY.md`
- Запрещено: evaluator, harness, TOOL_FUNCTIONS
- self_improve требует git (main или master)

---

## Фаза 0: Зерно (seed/)

**Цель:** Минимальный работающий агент за 1 день. Точка входа: `seed/main.py`.

### Что входит в зерно

```
seed/
├── main.py           # Точка входа, CLI-интерфейс (stdin/stdout)
├── llm.py            # OpenAI-compatible клиент → LLM endpoints
├── router.py         # Простой роутер: 80B primary, 35B fallback
├── tools.py          # 5 базовых инструментов (см. ниже)
├── loop.py           # Tool-calling цикл (recv → parse → exec → feed back)
├── prompts/
│   └── ENTRY.md      # Точка входа (Variant C: минимально — только дата)
├── pyproject.toml    # Зависимости: openai, httpx, pyyaml
└── tests/
    └── test_tools.py # Минимальные тесты
```

### 5 базовых инструментов зерна

```python
tools = [
    read_file(path) → str,          # Чтение файлов
    write_file(path, content) → ok,  # Запись файлов
    shell(command) → stdout+stderr,  # Bash-команды
    git_commit(msg, files) → hash,   # Git: add + commit
    run_tests() → pass/fail+output,  # pytest
]
```

Это всё. С этими пятью инструментами агент может: читать свой код, писать новый код, выполнять его, коммитить изменения, проверять результат.

### Точка входа (ENTRY.md, Variant C)

Минимальный system prompt — только дата. Никаких объяснений «кто ты», «что делать». Агент познаёт себя через tool schemas и исследование репозитория.

```
2026-03-09
```

Архив старого промпта: `seed/prompts/SEED.md.bak`

### Роутер зерна (router.py)

```python
class SeedRouter:
    providers = [
        {"name": "llm_80b",  "url": "http://localhost:1234/v1",  "priority": 1},
        {"name": "llm_35b",  "url": "http://localhost:8005/v1", "priority": 2},
    ]

    async def route(self, messages, tools=None):
        for provider in sorted(self.providers, key=lambda p: p["priority"]):
            if await self.health_check(provider):
                return await self.call(provider, messages, tools)
        raise AllProvidersDown()
```

---

## Фаза 1: Самосборка ядра

**Цель:** Агент, используя зерно, создаёт свои основные модули.
**Кто делает:** 80B планирует → 35B (2 слота) параллельно кодит → 80B ревьюит.

### Задание агенту (первый запуск)

```
Прочитай AGENT_ROADMAP.md. Ты сейчас — зерно.
Твоя первая задача: собрать модуль context.py по спецификации ниже.
После context.py → собери memory.py. После memory.py → собери agent.py.
Каждый модуль: напиши код → напиши тесты → запусти тесты → закоммить.
```

### Порядок самосборки модулей

```
Шаг 1: context.py
  ├─ Загрузка системного промпта
  ├─ Сборка контекста: static + semi-stable + dynamic
  ├─ Подсчёт токенов (tiktoken или приблизительный)
  └─ Тесты: проверка что контекст собирается

Шаг 2: memory.py
  ├─ identity.md — чтение/запись идентичности
  ├─ working-memory.md — рабочие заметки
  ├─ Хранение истории чата (JSONL)
  └─ Тесты: чтение/запись/ротация

Шаг 3: agent.py
  ├─ Основной оркестратор
  ├─ Подключает context + memory + loop + tools
  ├─ Управление раундами (max_rounds)
  └─ Тесты: один полный цикл tool call

Шаг 4: tools/registry.py
  ├─ Автообнаружение модулей в tools/
  ├─ get_tools() → список OpenAI-совместимых схем
  ├─ execute(name, args) → результат
  └─ Тесты: регистрация, вызов, неизвестный tool

Шаг 5: model_router.py (замена seed router.py)
  ├─ Полноценный роутер с health-check
  ├─ Классификация задач → выбор провайдера
  ├─ Метрики: latency, errors
  ├─ Конфигурация через YAML
  └─ Тесты: failover, health-check, routing logic
```

### Паттерн двух мозгов для самосборки

```
Человек даёт задачу (текст или AGENT_ROADMAP.md)
      │
      ▼
80B LLM: "Планирую. Для context.py нужно..."
      │ → Генерирует спецификацию + тесты
      │
      ├──────────────────────────────┐
      ▼                              ▼
35B LLM (слот 1):              35B LLM (слот 2):
"Пишу context.py"               "Пишу test_context.py"
      │                              │
      └──────────┬───────────────────┘
                 ▼
80B LLM: "Ревьюю..."
      │ → Проверяет код, находит проблемы
      │ → Если ОК → git commit
      │ → Если нет → отправляет фидбэк в 35B
      ▼
Тесты: pytest test_context.py
      │ → Если pass → следующий модуль
      │ → Если fail → 80B анализирует, 35B фиксит
```

---

## Фаза 2: Телеграм + Supervisor

**Цель:** Агент добавляет себе Telegram-интерфейс и процесс-менеджер.

### Задания агенту

```
Шаг 6: supervisor/telegram.py
  ├─ Telegram Bot API (python-telegram-bot или aiogram)
  ├─ Получение сообщений → постановка в очередь
  ├─ Отправка ответов
  └─ Команды: /status, /restart, /version

Шаг 7: supervisor/queue.py
  ├─ Очередь задач (asyncio.Queue или Redis)
  ├─ Приоритеты: user_message > consciousness > background
  ├─ Таймауты и ретрай
  └─ Тесты: постановка, выполнение, таймаут

Шаг 8: supervisor/state.py
  ├─ Персистентное состояние (JSON/SQLite)
  ├─ Сохранение между перезапусками
  └─ Метрики работы
```

---

## Фаза 3: RAG + Knowledge Base

**Цель:** Агент подключает векторный поиск через BGE на MacBook Pro.

```
Шаг 9: tools/embedding.py
  ├─ Клиент к BGE на localhost:9001 (LOCAL_AI_EMBEDDING_BASE_URL)
  ├─ Батчинг запросов
  └─ Кэширование результатов

Шаг 10: tools/reranker.py
  ├─ Клиент к BGE Reranker на localhost:9002 (LOCAL_AI_RERANKER_BASE_URL)
  └─ Интеграция с поиском

Шаг 11: tools/knowledge.py
  ├─ ChromaDB (встроенная, без сервера)
  ├─ Индексация memory/knowledge/
  ├─ Гибридный поиск: embedding + BM25
  ├─ Reranker как второй этап
  └─ Автоиндексация при изменениях
```

---

## Фаза 4: Consciousness + Самоэволюция

**Цель:** Агент обретает фоновое мышление и способность эволюционировать.

```
Шаг 12: consciousness.py
  ├─ Фоновый поток (daemon)
  ├─ Пробуждение по расписанию
  ├─ Ограниченный набор tools (read-only + working-memory)
  ├─ Бюджет: 10% от общего token budget
  ├─ Роутинг: 35B слот 2 (когда слот 1 занят основным)
  └─ Рефлексия: "что я могу улучшить?"

Шаг 13: tools/self_improve.py
  ├─ hot_reload(module) — перезагрузка модуля без рестарта
  ├─ propose_change(file, description) → diff
  ├─ apply_change(diff) → commit
  ├─ rollback(commit_hash) → revert
  ├─ evolution_log.md — что пробовали, что сработало
  └─ Защита: pre-commit проверки (ruff, pytest)

Шаг 14: Цикл самоэволюции
  ├─ Consciousness замечает паттерн ошибок
  ├─ Ставит задачу: "Улучшить обработку timeout в loop.py"
  ├─ 80B проектирует решение
  ├─ 35B реализует
  ├─ 80B ревьюит
  ├─ Тесты проходят → коммит
  └─ evolution_log.md обновлён
```

---

## Фаза 5: Расширенные возможности

**Цель:** Агент добавляет себе продвинутые фичи по мере необходимости.

```
Шаг 15+: Агент сам решает что строить дальше
  ├─ Browser automation (playwright)
  ├─ Vision (мультимодальность)
  ├─ ASR интеграция (LOCAL_AI_ASR_BASE_URL)
  ├─ GitHub API (issues, PRs)
  ├─ Web search (Brave API)
  ├─ Plugin-система
  ├─ Мониторинг (Prometheus/Grafana)
  └─ ...что угодно, что агент сочтёт нужным
```

---

## Критические правила самосборки

### 1. Каждое изменение — атомарный коммит

```
Плохо:  "Добавил context.py, memory.py, agent.py и всё починил"
Хорошо: "feat(context): add static block loading with token counting"
```

### 2. Тест ДО коммита

```
Цикл: write code → write test → run test → pass? → commit : fix
Никогда: write code → commit → "потом напишу тесты"
```

### 3. Откат при провале

```python
if tests_fail:
    git_revert(last_commit)
    analyze_failure()
    try_different_approach()  # max 3 попытки
    if still_failing:
        log_to_evolution_log("BLOCKED: ...")
        ask_human_for_help()
```

### 4. 80B проектирует, 35B реализует

```
НИКОГДА: 35B самостоятельно принимает архитектурные решения
ВСЕГДА:  80B → спецификация → 35B → код → 80B → ревью
```

### 5. Эволюционный лог

Каждая попытка изменения записывается:
```markdown
## 2026-03-09 14:30 — Попытка: добавить retry в llm.py
- Причина: timeout при длинных запросах к 35B
- Подход: exponential backoff (1s, 3s, 9s)
- Результат: ✅ тесты прошли, latency p99 снизился с 45s до 12s
- Коммит: abc1234
```

---

## Механики для надёжной самосборки

Механики из [Ekaterina v1](https://github.com/FUYOH666/Ekaterina), которые помогают агенту надёжно и долго познавать, улучшать и писать себя. Агент может добавить их по мере необходимости.

### Порядок добавления tools (рекомендуемый)

| # | Tool | Зачем |
|---|------|-------|
| 1 | shell | Выполнять команды, запускать тесты, git |
| 2 | git_commit | Сохранять изменения атомарно |
| 3 | run_tests | Проверять код перед коммитом |
| 4 | evolution_log | Читать/писать лог попыток — не повторять провалы |
| 5 | repo_patch | Search-replace вместо полной перезаписи — безопаснее для кода |

### evolution_log — формат

Файл `data/memory/evolution-log.md`:

```markdown
## 2026-03-09 14:30 — Попытка: добавить retry в llm.py
- Причина: timeout при длинных запросах
- Подход: exponential backoff (1s, 3s, 9s)
- Результат: ✅ тесты прошли
- Коммит: abc1234
```

### repo_patch — безопасное редактирование

Вместо `write_file(path, full_content)` — search-replace по паттерну. Меньше риск сломать файл.

```python
# Схема: repo_patch(path, old_string, new_string)
# Или: repo_multi_patch(path, [(old1, new1), (old2, new2)])
```

### Дисциплина коммитов

1. **Тест до коммита:** write code → write test → run test → pass? → commit : fix
2. **Откат при провале:** tests fail → git revert HEAD → analyze → try again (max 3)
3. **Атомарность:** один коммит = одно изменение. `feat(module): description`

### Дополнительно (по желанию)

- **state.json** — состояние между перезапусками (owner_id, tokens, version)
- **TOTAL_BUDGET** — лимит токенов
- **git_status / git_diff** — видеть изменения перед коммитом
- **run_python** — REPL для быстрых проверок
- **self-review** — проверка своего кода перед коммитом

---

## Метрики успеха

### Зерно (Фаза 0)
- [ ] seed.py запускается и отвечает на вопросы через CLI
- [ ] Оба LLM доступны и отвечают
- [ ] 5 базовых инструментов работают
- [ ] Первый самостоятельный коммит

### Ядро (Фаза 1)
- [ ] context.py — контекст собирается, токены считаются
- [ ] memory.py — идентичность и история персистентны
- [ ] agent.py — полный цикл: вопрос → tool calls → ответ
- [ ] model_router.py — failover между 80B и 35B работает
- [ ] ≥80% тестов проходят

### Telegram (Фаза 2)
- [ ] Бот отвечает в Telegram
- [ ] Очередь задач работает
- [ ] Состояние переживает рестарт

### RAG (Фаза 3)
- [ ] Embedding-запросы к BGE работают
- [ ] ChromaDB индексирует knowledge base
- [ ] Поиск возвращает релевантные результаты

### Самоэволюция (Фаза 4)
- [ ] Consciousness работает в фоне
- [ ] Агент сделал ≥1 самостоятельное улучшение
- [ ] evolution_log содержит записи

---

## Запуск: Как начать

### Вариант C (Evolutionary Boot) — текущий

```bash
# 1. Убедиться что LLM доступны
curl $LOCAL_AI_LLM_BASE_URL/models  # 80B
curl $LOCAL_AI_LLM_SECONDARY_BASE_URL/models  # 35B

# 2. Запуск
cd p1
uv run python seed/main.py

# 3. Первая команда (минимальная, ненаправляющая):
# "Начни"
# или: "Запустись. Изучи репозиторий. Действуй."

# 4. Наблюдать — агент сам решает что делать
```

Подробности: [BUILD_VARIANT_C.md](docs/archive/BUILD_VARIANT_C.md)

---

## Ссылки на исследования

- SICA (Self-Improving Coding Agent) — агенты редактируют свой код, +36% эффективности
- AgentEvolver (Alibaba, 2025) — self-questioning + self-navigating + self-attributing
- Darwin-Gödel Machine — эволюция из минимального зерна
- AlphaEvolve (DeepMind, 2025) — эволюционный кодинг-агент
- OpenHands — фреймворк для AI-агентов с самомодификацией
- EvoAgentX — экосистема самоэволюционирующих агентов

---

## Исследовательский план

Выжимка приоритетов. Полный документ: [docs/archive/RESEARCH_IMPROVEMENTS.md](docs/archive/RESEARCH_IMPROVEMENTS.md).

| # | Задача | Приоритет | Статус |
|---|--------|-----------|--------|
| 1 | ModelRouter — health-check, fallback 80B ↔ 35B | Высокий | Не начато |
| 2 | RAG-пайплайн — ChromaDB, BGE, гибридный поиск | Высокий | Частично (rag.py есть) |
| 3 | KV-Cache менеджмент | Средний | Не начато |
| 4 | Docker-compose оркестрация | Средний | Не начато |
| 5 | GBNF structured output для tool calling | Средний | Не начато |
| 6 | Speculative decoding | Низкий | Не начато |
| 7 | Метрики и мониторинг | Средний | Не начато |
| 8 | Consciousness v2 | Низкий | Частично (metacognitive monitor, forgetting curves) |
| 9 | Vision (мультимодальность) | Низкий | Не начато |
| 10 | Plugin-система для tools | Низкий | Не начато |

**Порядок:** Фаза 1 — ModelRouter + RAG. Фаза 2 — KV-Cache, GBNF, Docker. Фаза 3 — Метрики. Фаза 4 — Speculative, Consciousness, Vision, Plugins.

---

## Заметки

_Пополняется по ходу работы._

- ...
