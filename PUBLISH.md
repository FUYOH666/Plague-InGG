# Публикация на GitHub

## Перед push

1. **Проверьте .gitignore** — `.env`, `data/logs/`, `data/runner/`, персональные `data/memory/*.md`, `docs/archive/` не должны попасть в репозиторий
2. **Проверьте .env** — не коммитьте. Убедитесь, что он в .gitignore
3. **IP и токены** — все URL берутся из .env, в коде только localhost по умолчанию

### Pre-push verification

Перед push выполните проверку на утечку IP и токенов (должно быть 0 результатов):

```bash
# Проверка на утечку TailScale IP (100.x.x.x)
rg "100\.\d+\.\d+\.\d+" --glob '!*.git' --glob '!.env' .
# или grep:
grep -rE "100\.\d+\.\d+\.\d+" . --exclude-dir=.git --exclude=.env 2>/dev/null || true

# Проверка на токены (примеры — замените на свои паттерны)
rg "8546906086|BSAGbJHXh|AAE046kEEFPM4zjFvU6tOE1y6os55Pn0anw" .
```

## GitHub MCP (Cursor)

GitHub MCP в Cursor: `search_repositories` работает, `create_repository` требует authentication. Настройте токен: Settings → MCP → user-github → env: `GITHUB_TOKEN` или `GITHUB_PERSONAL_ACCESS_TOKEN`.

## Создание репозитория

1. Создайте репозиторий на GitHub: https://github.com/new
   - Name: `Plague-InGG`
   - Description: `Self-evolving AI agent. Minimal seed, emergent identity. Join the evolution.`
   - Public
   - Без README (у нас уже есть)

2. Добавьте remote и push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/Plague-InGG.git
# или если origin уже есть:
git remote set-url origin https://github.com/YOUR_USERNAME/Plague-InGG.git

git add .
git status   # проверьте, что .env, data/logs, docs/archive не в списке
git commit -m "Initial: Plague InGG — self-evolving agent (MIT)"
git push -u origin main
```

## Что не попадёт в репозиторий (см. .gitignore)

- `.env` — токены, ключи, ваши URL
- `data/logs/` — логи сессий
- `data/runner/` — eval_result, evolution_log.jsonl
- `data/memory/identity.md`, `working-memory.md`, `evolution-log.md`, `session-history.md`, `goals.md`
- `docs/archive/` — архив с IP
