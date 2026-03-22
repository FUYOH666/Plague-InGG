"""Surgical single replacement in a text file (safer than full write_file)."""

from pathlib import Path

TOOL_SPEC = {
    "name": "str_replace_file",
    "description": (
        "Replace exactly one occurrence of old_string with new_string in a file. "
        "Fails if zero or multiple matches. Cannot modify kernel/core.py."
    ),
    "params": {
        "path": "File path relative to project root",
        "old_string": "Text to find (must appear exactly once)",
        "new_string": "Replacement text",
    },
}

ROOT = Path(__file__).resolve().parent.parent
PROTECTED = ROOT / "kernel" / "core.py"


def execute(params: dict) -> str:
    rel_path = params.get("path", "")
    old = params.get("old_string")
    new = params.get("new_string")
    if old is None or new is None:
        return "old_string and new_string are required."
    if not rel_path:
        return "No path specified."

    target = (ROOT / rel_path).resolve()
    if not str(target).startswith(str(ROOT)):
        return "Access denied: outside project directory."
    if target == PROTECTED:
        return "🧬 PROTECTED: kernel/core.py cannot be modified."
    if not target.is_file():
        return f"File not found: {rel_path}"

    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        return "❌ old_string not found in file."
    if count > 1:
        return f"❌ old_string matches {count} times; must be unique. Narrow the snippet."

    updated = text.replace(old, new, 1)
    target.write_text(updated, encoding="utf-8")
    return f"✅ Replaced 1 occurrence in {rel_path} ({len(updated)} chars)."

