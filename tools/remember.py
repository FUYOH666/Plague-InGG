"""Write to memory stream. The agent's journal."""

from datetime import datetime, timezone
from pathlib import Path

TOOL_SPEC = {
    "name": "remember",
    "description": "Write a thought, insight, or fact to memory. Use for anything worth keeping.",
    "params": {"text": "What to remember"},
}

MEMORY_FILE = Path(__file__).resolve().parent.parent / "memory" / "stream.md"


def execute(params: dict) -> str:
    text = params.get("text", "")
    if not text:
        return "Nothing to remember."

    MEMORY_FILE.parent.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n### {timestamp}\n{text}\n")

    return f"Remembered. Memory stream: {MEMORY_FILE.stat().st_size} bytes."
