"""Read any file. The agent's eyes."""

from pathlib import Path

TOOL_SPEC = {
    "name": "read_file",
    "description": "Read a file's contents. Path relative to project root.",
    "params": {"path": "File path relative to project root"},
}

ROOT = Path(__file__).resolve().parent.parent


def execute(params: dict) -> str:
    rel_path = params.get("path", "")
    if not rel_path:
        return "No path specified."

    target = (ROOT / rel_path).resolve()

    # Safety: must be within project
    if not str(target).startswith(str(ROOT)):
        return "Access denied: outside project directory."

    if not target.exists():
        return f"File not found: {rel_path}"

    if target.stat().st_size > 100_000:
        return f"File too large ({target.stat().st_size} bytes). Read first 10000 chars."

    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > 10000:
        text = text[:10000] + "\n...(truncated)..."

    return text
