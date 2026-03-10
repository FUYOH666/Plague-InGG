# Contributing to Plague InGG

Thank you for your interest. Plague InGG is a self-evolving AI agent. We welcome contributions from everyone.

## How to contribute

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/Plague-InGG.git`
3. **Create a branch**: `git checkout -b feature/your-idea`
4. **Make changes** — code, docs, ideas
5. **Run tests**: `uv run pytest seed/tests/ -q`
6. **Commit** and **Push**
7. **Open a Pull Request**

See [good first issues](https://github.com/FUYOH666/Plague-InGG/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).

## Minimal setup (no LLM)

If you don't have LLM/Embedding — you can still contribute and run basic tests:

```bash
uv sync
uv run pytest seed/tests/ -q   # 32 tests, no external services required
```

Capability benchmark (RAG, embedding) requires .env with service URLs. For PRs, pytest is enough.

## What to improve

- **Tools** — add a new tool via `add_tool` or in `seed/tools.py`
- **Prompts** — `seed/prompts/ENTRY.md` defines agent behavior
- **RAG, routing** — extend search and model selection
- **Documentation** — README, AGENT_ROADMAP, examples
- **Ideas** — Open issues with evolution proposals

## Rules

- Tests must pass: `uv run pytest seed/tests/`
- Capability benchmark: `uv run python scripts/capability_benchmark.py` (if you have .env)
- Don't commit `.env` — only `.env.example` with placeholders

## Code of Conduct

Be respectful. Code criticism — yes. Personal attacks — no.

## Questions

Open an issue with label `question` or `discussion`. Good first issues: `good-first-issue`.

---

<details>
<summary>Русский</summary>

Спасибо за интерес к проекту. Plague InGG — это самоэволюционирующий AI-агент. Мы приветствуем вклад от всех.

Как присоединиться: Fork → Clone → Ветка → Изменения → Тесты → PR. См. good first issues выше.

</details>
