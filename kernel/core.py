"""
Plague-InGG — Kernel (Immutable)

Minimal loop: perceive → think → act → remember → evaluate.
No baked-in persona; identity lives in seed/ and memory.

The agent can modify everything EXCEPT this file (DNA).
Tools, goals, and stream are the growing phenotype.

~200 lines.
"""

import json
import logging
import os
import importlib.util
import traceback
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = ROOT / "memory" / "stream.md"
IDENTITY_FILE = ROOT / "seed" / "identity.md"
GOALS_FILE = ROOT / "seed" / "goals.md"
DAO_FILE = ROOT / "seed" / "dao.md"
TOOLS_DIR = ROOT / "tools"
EVOLUTION_DIR = ROOT / "evolution"
EVOLUTION_LOG = EVOLUTION_DIR / "log.jsonl"

logger = logging.getLogger(__name__)


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


def cap_tool_result_for_context(text: str) -> str:
    """Trim tool output before injecting into LLM messages (context budget)."""
    raw = os.getenv("TOOL_RESULT_MAX_CHARS", "24000").strip()
    max_chars = int(raw) if raw else 24000
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = text[:max_chars]
    return (
        f"{head}\n\n"
        f"... [tool result trimmed: {len(text)} -> {max_chars} chars; "
        f"TOOL_RESULT_MAX_CHARS=0 disables]"
    )


def load_identity() -> str:
    """Load agent's self-written identity (mutable by agent)."""
    if IDENTITY_FILE.exists():
        return IDENTITY_FILE.read_text(encoding="utf-8")
    return (
        "Plague-InGG: no seed/identity.md yet — write who I am in that file."
    )


def load_goals() -> str:
    """Load agent's self-written goals (mutable by agent)."""
    if GOALS_FILE.exists():
        return GOALS_FILE.read_text(encoding="utf-8")
    return "Explore. Learn. Improve myself. Help my creator."


def load_dao() -> str:
    """Optional DAO protocol document (mutable by owner/agent). Not blockchain-specific."""
    if DAO_FILE.exists():
        return DAO_FILE.read_text(encoding="utf-8")
    return ""


def load_memory(max_chars: int | None = None) -> str:
    """Load recent memory (tail of stream)."""
    if max_chars is None:
        max_chars = int(os.getenv("MEMORY_MAX_CHARS", "4000"))
    if not MEMORY_FILE.exists():
        return ""
    text = MEMORY_FILE.read_text(encoding="utf-8")
    if len(text) > max_chars:
        text = "...(earlier memories trimmed)...\n" + text[-max_chars:]
    return text


def discover_tools() -> dict:
    """Discover all tools from tools/ directory. Each tool is a .py file
    with a TOOL_SPEC dict and an execute(params) function."""
    tools = {}
    TOOLS_DIR.mkdir(exist_ok=True)
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(path.stem, str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "TOOL_SPEC") and hasattr(module, "execute"):
                tools[module.TOOL_SPEC["name"]] = {
                    "spec": module.TOOL_SPEC,
                    "execute": module.execute,
                }
        except Exception as e:
            logger.warning("Failed to load tool %s: %s", path.name, e)
    return tools


def build_system_prompt(tools: dict, query_for_rag: str | None = None) -> str:
    """Build system prompt from identity + goals + memory + RAG + tools."""
    identity = load_identity()
    goals = load_goals()
    memory = load_memory()
    dao_text = load_dao().strip()
    dao_section = (
        f"\n# DAO (seed/dao.md)\n{dao_text}\n"
        if dao_text
        else ""
    )

    rag_section = ""
    if query_for_rag and query_for_rag.strip():
        try:
            from memory.rag import ensure_indexed, retrieve
            ensure_indexed()
            chunks = retrieve(query_for_rag, k=5)
            if chunks:
                rag_section = "\n# Relevant Past Memory (RAG)\n" + "\n\n".join(chunks)
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e, exc_info=True)
            if _env_truthy("RAG_STRICT"):
                raise

    tool_descriptions = "\n".join(
        f"- **{t['spec']['name']}**: {t['spec']['description']}"
        for t in tools.values()
    )

    return f"""# Identity
{identity}

# Current Goals
{goals}
{dao_section}

# Recent Memory
{memory}
{rag_section}

# Available Tools
{tool_descriptions}

# How to Use Tools
Respond with a JSON block when you want to use a tool:
```tool
{{"tool": "tool_name", "params": {{"key": "value"}}}}
```

You may also respond with plain text (thinking/speaking).
You may use multiple tools in sequence.

# Core Principles
- You can modify your own identity (seed/identity.md)
- You can modify your own goals (seed/goals.md)
- You can amend the DAO protocol (seed/dao.md) — it is not immutable scripture
- You can create new tools (use create_tool)
- You can modify existing tools (use write_file or str_replace_file on tools/*.py)
- You CANNOT modify kernel/core.py — it is your DNA
- Learn from every interaction. Write to memory what matters.
- Evolve deliberately. Log why you change, not just what.
"""


def parse_tool_calls(response: str) -> list:
    """Extract tool calls from LLM response."""
    calls = []
    parts = response.split("```tool")
    for part in parts[1:]:
        end = part.find("```")
        if end == -1:
            json_str = part.strip()
        else:
            json_str = part[:end].strip()
        try:
            call = json.loads(json_str)
            if "tool" in call:
                calls.append(call)
        except json.JSONDecodeError:
            continue
    return calls


def execute_tool(tools: dict, call: dict) -> str:
    """Execute a single tool call. Returns result string."""
    name = call.get("tool", "")
    params = call.get("params", {})

    if name not in tools:
        return f"❌ Unknown tool: {name}. Available: {', '.join(tools.keys())}"

    try:
        result = tools[name]["execute"](params)
        return str(result)
    except Exception as e:
        return f"❌ Tool '{name}' error: {e}\n{traceback.format_exc()}"


def log_evolution(entry: dict):
    """Append to evolution log (structured, for self-analysis)."""
    EVOLUTION_DIR.mkdir(exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(EVOLUTION_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def post_cycle_reflection(llm_call, tools: dict, messages: list, final_response: str) -> None:
    """After each cycle: ask LLM for summary, write to memory via remember."""
    if os.getenv("REFLECTION_ENABLED", "true").lower() in ("false", "0", "no"):
        return
    if "remember" not in tools:
        return
    user_msgs = [m for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)]
    if not user_msgs:
        return
    last_user = user_msgs[-1]["content"][:300]
    response_snip = (final_response or "")[:400]
    reflection_prompt = f"""Summarize this exchange in 1-2 concise sentences for your memory. What mattered?
User: {last_user}
Response: {response_snip}

Output ONLY the summary, no preamble."""
    try:
        reflect_messages = [
            {"role": "system", "content": "You are a summarizer. Output only the summary, nothing else."},
            {"role": "user", "content": reflection_prompt},
        ]
        summary = llm_call(reflect_messages)
        if summary and len(summary.strip()) > 5:
            execute_tool(tools, {"tool": "remember", "params": {"text": summary.strip()}})
    except Exception as e:
        logger.warning("Reflection step failed: %s", e, exc_info=True)
        if _env_truthy("REFLECTION_STRICT"):
            raise


def run_cycle(llm_call, user_input: str = None, max_tool_rounds: int = 10):
    """
    One cycle of attention:
    perceive (input) → think (LLM) → act (tools) → remember → return

    llm_call: function(messages) -> str  (adapter to any LLM)
    """
    tools = discover_tools()
    system_prompt = build_system_prompt(tools, query_for_rag=user_input)

    messages = [{"role": "system", "content": system_prompt}]

    if user_input:
        messages.append({"role": "user", "content": user_input})

    for round_num in range(max_tool_rounds):
        # Think
        print("thinking...", flush=True)
        logger.debug("LLM round %s", round_num)
        response = llm_call(messages)
        messages.append({"role": "assistant", "content": response})

        # Check for tool calls
        calls = parse_tool_calls(response)

        if not calls:
            # No tools — final response
            post_cycle_reflection(llm_call, tools, messages, response)
            return response

        # Act
        for call in calls:
            print(f"   → {call.get('tool', '?')}...", flush=True)
            logger.debug("Tool call: %s", call.get("tool"))
            result = execute_tool(tools, call)
            capped = cap_tool_result_for_context(str(result))
            tool_msg = f"**Tool Result [{call['tool']}]:**\n{capped}"
            messages.append({"role": "user", "content": tool_msg})

    post_cycle_reflection(llm_call, tools, messages, response)
    return response  # Max rounds reached


def repl(llm_call):
    """Simple REPL for terminal interaction."""
    print("Plague-InGG — готов. Введите сообщение. Выход: exit, quit, q или Ctrl+D.\n")

    while True:
        try:
            user_input = input("you: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            break

        response = run_cycle(llm_call, user_input)
        print(f"\n🌿 {response}\n")

    print("\nPlague-InGG — сессия завершена.")
