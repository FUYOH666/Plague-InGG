"""Tool-calling loop — reloads tools each round so agent can add new ones."""

from __future__ import annotations

import importlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Run from project root, seed/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAFETY_CAP = 5000
CONTEXT_COMPRESS_THRESHOLD = 40_000  # estimated tokens
CONTEXT_KEEP_RECENT = 10  # keep last N messages when compressing

from router import ModelRouter


def _session_log_path() -> Path:
    """Path for this session's log file."""
    logs_dir = PROJECT_ROOT / "data" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return logs_dir / f"session_{ts}.log"


def _session_write(path: Path, text: str) -> None:
    """Append to session log."""
    try:
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        path.write_text(existing + text + "\n", encoding="utf-8")
    except Exception:
        pass


def _get_tools_module():
    """Import tools module for reload."""
    import tools as tools_module
    return tools_module


def _estimate_tokens(messages: list[dict]) -> int:
    """Approximate token count: chars / 3 for mixed text."""
    total = 0
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, str):
            total += len(content)
        for tc in m.get("tool_calls") or []:
            fn = tc.get("function", {})
            total += len(fn.get("name", "")) + len(str(fn.get("arguments", "")))
    return total // 3


def _format_messages_for_summary(messages: list[dict]) -> str:
    """Format messages as readable text for summarization."""
    lines = []
    for m in messages:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role == "user" and content:
            lines.append(f"User: {content[:2000]}")
        elif role == "assistant" and content:
            lines.append(f"Assistant: {content[:2000]}")
        elif role == "tool":
            lines.append(f"Tool result: {content[:500]}...")
    return "\n\n".join(lines)


def _compress_messages(router: ModelRouter, messages: list[dict], verbose: bool) -> list[dict]:
    """Summarize old messages, replace with compact block. Keep system + last N."""
    n = len(messages)
    keep = min(CONTEXT_KEEP_RECENT, n - 3)
    if keep < 1:
        return messages

    to_compress = messages[2:-keep]
    if not to_compress:
        return messages

    dialog_text = _format_messages_for_summary(to_compress)
    if len(dialog_text) < 500:
        return messages

    summarizer_messages = [
        {"role": "system", "content": "Суммаризируй диалог. Выдели ключевые факты, решения, изменения файлов, выводы. Кратко, 200-400 слов."},
        {"role": "user", "content": dialog_text},
    ]

    try:
        response = router.chat(summarizer_messages, tools=None, temperature=0.3, task="default")
        summary = (response.content or "").strip()
        if not summary:
            return messages

        if verbose:
            _log(f"  [compress] {len(to_compress)} msgs → summary {len(summary)} chars")

        compressed_block = {"role": "user", "content": f"[Ранее в диалоге:\n\n{summary}\n\nПродолжи с этого места.]"}
        return [messages[0], compressed_block] + messages[-keep:]
    except Exception as e:
        if verbose:
            _log(f"  [compress] failed: {e}")
        return messages


def _detect_stuck(tools_used: list[str], tool_read_paths: list[str]) -> bool:
    """Detect if agent is spinning: same read_file path 2+ times, or same tool 3+ in a row."""
    if len(tool_read_paths) != len(set(tool_read_paths)):
        return True  # duplicate read paths
    if len(tools_used) >= 3:
        for i in range(len(tools_used) - 2):
            if tools_used[i] == tools_used[i + 1] == tools_used[i + 2]:
                return True
    return False


def _append_session_history(user_message: str, rounds: int, tools_list: list[str], result: str) -> None:
    """Append session summary to data/memory/session-history.md."""
    history_path = PROJECT_ROOT / "data" / "memory" / "session-history.md"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    tools_str = ", ".join(tools_list) if tools_list else "(none)"
    result_preview = (result[:200] + "...") if len(result) > 200 else result
    block = (
        f"\n## {ts} — User: {user_message[:80]}\n"
        f"- Rounds: {rounds}\n"
        f"- Tools: {tools_str}\n"
        f"- Result: {result_preview}\n"
    )
    try:
        existing = history_path.read_text(encoding="utf-8") if history_path.exists() else ""
        history_path.write_text(existing + block, encoding="utf-8")
    except Exception:
        pass


PAUSED_SESSION_PATH = PROJECT_ROOT / "data" / "memory" / "paused_session.json"
PAUSED_MAGIC = "__PAUSED__"


def run_loop(
    router: ModelRouter,
    system_prompt: str,
    user_message: str,
    max_rounds: int = 0,
    temperature: float = 0.7,
    verbose: bool = True,
    summary_queue=None,
    chat_id=None,
    resume_state=None,
    human_reply: str | None = None,
) -> str:
    """
    Execute one complete agent loop.
    max_rounds=0 means unlimited (with SAFETY_CAP). Reloads tools each round.
    resume_state + human_reply: resume from ask_human pause.
    """
    from tools import AskHumanPause, _loop_context

    tools_module = _get_tools_module()
    tools_module._loop_context = {
        "summary_queue": summary_queue,
        "chat_id": chat_id,
        "pending_tool_call_id": "",
    }

    if resume_state and human_reply is not None:
        messages = resume_state["messages"]
        messages.append({
            "role": "tool",
            "tool_call_id": resume_state["ask_human_tool_call_id"],
            "content": human_reply,
        })
        session_path = Path(resume_state["session_path"])
        tools_used = list(resume_state["tools_used"])
        round_num = resume_state["round_num"]
        effective_max = resume_state.get("effective_max", SAFETY_CAP)
        round_display = resume_state.get("round_display", "")
    else:
        session_path = _session_log_path()
        tools_used = []
        effective_max = max_rounds if max_rounds > 0 else SAFETY_CAP
        round_display = f"/{max_rounds}" if max_rounds > 0 else ""

        _session_write(
            session_path,
            f"=== Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n"
            f"User: {user_message}\n",
        )
        print(f"  Log: {session_path}", file=sys.stderr)

        _task_keywords = (
            "сделай", "добавь", "почини", "запусти", "напиши", "создай",
            "исправь", "реализуй", "удали", "измени", "рефактори", "переделай",
        )
        _msg_lower = user_message.lower()
        _is_simple = (
            len(user_message) < 100
            and not any(kw in _msg_lower for kw in _task_keywords)
        )
        if _is_simple:
            bootstrap = (
                "[Ответь кратко. При необходимости прочитай data/memory/evolution-log.md.]\n\n"
            )
        else:
            bootstrap = (
                "[Сначала исследуй репозиторий: list_dir, read_file. "
                "Кто ты? Что можешь? Перед ответом прочитай data/memory/evolution-log.md, "
                "data/memory/session-history.md, data/memory/working-memory.md и data/memory/goals.md — "
                "что ты уже делала, какие цели. Потом ответь.]\n\n"
            )
        if summary_queue is not None:
            bootstrap = (
                "[Telegram. Пиши кратко, по сути, живым языком. Без длинных списков и заголовков, если не нужны. Суть важнее объёма.]\n\n"
            ) + bootstrap
        wrapped_message = bootstrap + f"Пользователь: {user_message}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": wrapped_message},
        ]
        round_num = 0

    empty_response_retried = False
    stuck_hint_injected = False
    tool_read_paths: list[str] = []
    while True:
        round_num += 1
        if round_num > effective_max:
            break

        if round_num > 6 and not stuck_hint_injected and _detect_stuck(tools_used, tool_read_paths):
            stuck_hint_injected = True
            hint = "Похоже, ты зациклилась. Рассмотри ответ пользователю или ask_human, если нужна помощь."
            _session_write(session_path, f"  -> [stuck hint] {hint}")
            messages.append({"role": "user", "content": hint})

        if verbose:
            _log(f"--- round {round_num}{round_display} ---")

        # Reload tools each round — agent may have added new ones
        importlib.reload(tools_module)
        tool_schemas, _ = tools_module.get_tools()

        # Reflection (rounds 6, 11, 16...) → 80B LLM. Rest → 35B LLM.
        is_reflect_round = round_num > 1 and round_num % 5 == 1
        task = "reflect" if is_reflect_round else "default"
        if verbose and is_reflect_round:
            _log(f"  [80B LLM] reflection")

        # Компрессия контекста при превышении порога (раз в 10 раундов)
        if round_num % 10 == 0 and _estimate_tokens(messages) > CONTEXT_COMPRESS_THRESHOLD:
            messages = _compress_messages(router, messages, verbose)

        # Call LLM
        response = router.chat(
            messages, tools=tool_schemas, temperature=temperature, task=task
        )

        # Metacognitive monitor (Blueprint): optional confidence/repetition check before tool execution
        if (
            response.tool_calls
            and round_num > 3
            and os.getenv("METACOGNITIVE_CHECK", "").lower() in ("true", "1", "yes")
        ):
            last_content = (response.content or "").strip()
            if last_content:
                try:
                    meta_messages = [
                        {"role": "system", "content": "Answer only valid JSON. No other text."},
                        {"role": "user", "content": (
                            "Evaluate the assistant's last response. Reply with JSON only: "
                            '{"confidence": 1-5, "repetition": true/false}. '
                            "confidence: 1=very uncertain, 5=very confident. "
                            "repetition: true if repeating itself or looping."
                        )},
                        {"role": "assistant", "content": last_content[:1500]},
                        {"role": "user", "content": "JSON:"},
                    ]
                    meta_resp = router.chat(
                        meta_messages, tools=None, max_tokens=80, temperature=0, task="reflect"
                    )
                    meta_text = (meta_resp.content or "").strip()
                    for start in ("{", "```json"):
                        if start in meta_text:
                            meta_text = meta_text[meta_text.find(start):]
                            if meta_text.startswith("```"):
                                meta_text = meta_text.replace("```json", "").replace("```", "").strip()
                            break
                    meta = json.loads(meta_text)
                    conf = int(meta.get("confidence", 5))
                    rep = meta.get("repetition", False)
                    if conf < 3 or rep:
                        hint = (
                            "Metacognitive check: low confidence or repetition detected. "
                            "Reconsider your plan before executing tools."
                        )
                        messages.append({"role": "user", "content": hint})
                        if verbose:
                            _log(f"  [metacog] {hint}")
                        continue
                except (json.JSONDecodeError, KeyError, TypeError):
                    pass

        # If LLM returned text without tool calls — we're done
        if not response.tool_calls:
            if verbose and response.content:
                _log(f"[response] {response.content[:200]}...")
            out = response.content or ""
            if not out.strip():
                if not empty_response_retried:
                    empty_response_retried = True
                    _session_write(session_path, f"\n--- Round {round_num}: FINAL (empty, retrying) ---")
                    messages.append({
                        "role": "user",
                        "content": "Твой предыдущий ответ был пуст. Ответь пользователю.",
                    })
                    continue
                fallback = "Извини, не удалось сформулировать ответ. Попробуй переформулировать вопрос."
                _session_write(session_path, f"\n--- Round {round_num}: FINAL (empty, fallback) ---\n{fallback}")
                _append_session_history(user_message, round_num, tools_used, fallback)
                return fallback
            _session_write(session_path, f"\n--- Round {round_num}: FINAL ---\n{out}")
            _append_session_history(user_message, round_num, tools_used, out)
            return out

        # LLM wants to call tools
        assistant_msg = {"role": "assistant", "content": response.content or ""}
        assistant_msg["tool_calls"] = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": _to_json_str(tc["arguments"]),
                },
            }
            for tc in response.tool_calls
        ]
        messages.append(assistant_msg)

        # Execute tool calls (parallel when PARALLEL_TOOLS=true and 2+ calls)
        importlib.reload(tools_module)
        _session_write(session_path, f"\n--- Round {round_num} ---")
        round_steps: list[tuple[str, dict, str]] = []
        use_parallel = (
            os.getenv("PARALLEL_TOOLS", "").lower() in ("1", "true", "yes")
            and len(response.tool_calls) >= 2
        )

        def run_one(tc):
            tools_module._loop_context["pending_tool_call_id"] = tc["id"]
            name = tc["name"]
            args = tc["arguments"]
            result = tools_module.execute_tool(name, args)
            return tc["id"], name, args, result

        try:
            if use_parallel:
                results_by_id = {}
                with ThreadPoolExecutor(max_workers=2) as ex:
                    futures = {ex.submit(run_one, tc): tc for tc in response.tool_calls}
                    for fut in as_completed(futures):
                        tc_id, name, args, result = fut.result()
                        results_by_id[tc_id] = (name, args, result)

                for tc in response.tool_calls:
                    tc_id = tc["id"]
                    name, args, result = results_by_id[tc_id]
                    tools_used.append(name)
                    if len(result) > 10_000:
                        result = result[:10_000] + f"\n... [truncated, {len(result)} chars total]"
                    round_steps.append((name, args, result))
                    if verbose:
                        _log(f"[tool] {name}({str(args)[:100]})")
                        _log(f"[result] {result[:150]}...")
                    _session_write(session_path, f"  [tool] {name}({str(args)[:300]})")
                    _session_write(session_path, f"  [result] {result[:500]}...")
                    messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})
            else:
                for tc in response.tool_calls:
                    tools_module._loop_context["pending_tool_call_id"] = tc["id"]
                    name = tc["name"]
                    tools_used.append(name)
                    args = tc["arguments"]
                    if verbose:
                        args_preview = str(args)[:100]
                        _log(f"[tool] {name}({args_preview})")
                    _session_write(session_path, f"  [tool] {name}({str(args)[:300]})")
                    result = tools_module.execute_tool(name, args)
                    if len(result) > 10_000:
                        result = result[:10_000] + f"\n... [truncated, {len(result)} chars total]"
                    round_steps.append((name, args, result))
                    if verbose:
                        _log(f"[result] {result[:150]}...")
                    result_preview = result[:500] + ("..." if len(result) > 500 else "")
                    _session_write(session_path, f"  [result] {result_preview}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })
        except AskHumanPause as e:
            PAUSED_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            state = {
                "chat_id": chat_id,
                "messages": messages,
                "round_num": round_num,
                "tools_used": tools_used,
                "session_path": str(session_path),
                "user_message": user_message,
                "ask_human_tool_call_id": e.tool_call_id or (
                    response.tool_calls[0]["id"] if response.tool_calls else ""
                ),
                "effective_max": effective_max,
                "round_display": round_display,
            }
            PAUSED_SESSION_PATH.write_text(_json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return PAUSED_MAGIC

        for name, args, _ in round_steps:
            if name in ("read_file", "list_dir"):
                path = args.get("path", "")
                if path is not None:
                    tool_read_paths.append(str(path))

        if summary_queue is not None:
            summary = _format_telegram_summary(round_num, round_steps)
            try:
                summary_queue.put_nowait(summary)
            except Exception:
                pass

        # Reflection every 5 rounds
        if round_num > 0 and round_num % 5 == 0:
            refl = f"[Рефлексия, раунд {round_num}{round_display}: Кто ты? Что обнаружил? Что изменить? Выбери один пункт из «Что изменить» и сделай его сейчас — write_file, repo_patch или add_tool.]"
            _session_write(session_path, f"  -> {refl}")
            messages.append({"role": "user", "content": refl})

    if verbose:
        _log(f"[!] Max rounds ({effective_max}) reached")
    _session_write(session_path, f"\n--- Max rounds ({effective_max}) reached ---")
    fallback = "[max rounds reached — task may be incomplete]"
    _append_session_history(user_message, round_num, tools_used, fallback)
    return fallback


def _to_json_str(obj) -> str:
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False)


def _short_args(args: dict) -> str:
    """Compact string for tool args, max ~80 chars."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        s = str(v)
        if len(s) > 40:
            s = s[:37] + "..."
        parts.append(f"{k}={s}")
    return ", ".join(parts)[:80]


def _action_desc(name: str, args: dict) -> str:
    """Human-readable action for Telegram."""
    arg = args.get("path") or args.get("query") or args.get("code", "")[:30]
    if name == "list_dir":
        return f"исследовала {arg or 'корень'}"
    if name == "read_file":
        return f"прочитала {arg}"
    if name == "write_file":
        return f"записала в {arg}"
    if name == "repo_patch":
        return f"изменила {arg}"
    if name == "safe_edit":
        return f"безопасно изменила {arg}"
    if name == "evolution_log":
        return "записала в evolution_log"
    if name == "working_memory":
        return "обновила память"
    if name == "run_tests":
        return "запустила тесты"
    if name == "run_python":
        return "выполнила код"
    if name == "git_commit":
        msg = args.get("message", "")[:40]
        return f"коммит: {msg}"
    if name == "git_init":
        return "инициализировала git"
    if name == "git_status":
        return "проверила git"
    if name == "web_search":
        return f"искала в вебе: {arg[:35]}"
    if name in ("github_search_repos", "github_search_code"):
        return f"искала на GitHub: {arg[:35]}"
    if name == "github_read_file":
        repo = f"{args.get('owner', '')}/{args.get('repo', '')}"
        return f"прочитала с GitHub {repo}"
    if name == "transcribe_audio":
        return f"транскрибировала {args.get('path', '')}"
    if name == "embedding":
        return "создала эмбеддинги"
    if name == "rerank":
        return "реранжировала документы"
    if name == "shell":
        cmd = str(args.get("command", ""))[:30]
        return f"выполнила: {cmd}"
    if name == "rag_index":
        return f"проиндексировала {args.get('path', '')}"
    if name == "rag_index_evolution":
        return "проиндексировала эволюцию"
    if name == "rag_search":
        return f"искала в RAG: {args.get('query', '')[:35]}"
    if name == "rag_list":
        return "список RAG"
    if name == "rag_fetch":
        return f"загрузила из RAG: {args.get('doc_id', '')[:30]}"
    if name == "rag_index_docs":
        return f"проиндексировала docs: {args.get('library_name', '')}"
    if name == "set_goal":
        return f"добавила цель: {args.get('description', '')[:35]}"
    if name == "read_goals":
        return "прочитала цели"
    if name == "add_tool":
        return f"добавила tool: {args.get('name', '')}"
    if name == "ask_human":
        return f"спросила: {args.get('question', '')[:40]}"
    if name == "browse_web":
        act = args.get("action", "")
        if act == "open":
            return f"открыла {args.get('url', '')[:35]}"
        return f"browse: {act}"
    return f"{name}({_short_args(args)[:40]})"


def _result_hint(name: str, result: str) -> str:
    """Short result hint for Telegram (max ~50 chars)."""
    if "[PASSED]" in result:
        return "тесты прошли"
    if "[FAILED]" in result:
        return "тесты упали"
    if result.startswith("OK:"):
        return result.split("\n")[0][:50]
    if result.startswith("[ERROR]"):
        return "ошибка"
    if name == "list_dir":
        n = len([x for x in result.split("\n") if x.strip()])
        return f"найдено {n} файлов"
    if name == "read_file" and result:
        first = result.split("\n")[0].strip()[:45]
        return first + ("..." if len(first) >= 45 else "")
    if len(result) > 50:
        return result[:47] + "..."
    return result[:50] if result else ""


def _format_telegram_summary(
    round_num: int,
    round_steps: list[tuple[str, dict, str]],
) -> str:
    """Формат: Шаг N: действие → результат; действие → результат."""
    parts = []
    for name, args, result in round_steps:
        action = _action_desc(name, args)
        hint = _result_hint(name, result)
        if hint:
            parts.append(f"{action} → {hint}")
        else:
            parts.append(action)
    combined = "; ".join(parts)[:350]
    return f"Шаг {round_num}: {combined}"


def _log(text: str):
    print(text, file=sys.stderr, flush=True)
