"""List directory contents."""

from pathlib import Path

TOOL_SPEC = {
    "name": "list_dir",
    "description": "List files and directories. Path relative to project root.",
    "params": {"path": "Directory path (default: root)"},
}

ROOT = Path(__file__).resolve().parent.parent


def execute(params: dict) -> str:
    rel = params.get("path", ".")
    target = (ROOT / rel).resolve()
    if not str(target).startswith(str(ROOT)):
        return "Access denied."
    if not target.is_dir():
        return f"Not a directory: {rel}"
    items = sorted(target.iterdir())
    lines = []
    for item in items:
        prefix = "📁" if item.is_dir() else "📄"
        size = f" ({item.stat().st_size}b)" if item.is_file() else ""
        lines.append(f"{prefix} {item.name}{size}")
    return "\n".join(lines) if lines else "(empty)"
