"""Write/overwrite a file. The agent's hands. Enables self-modification."""

from pathlib import Path

TOOL_SPEC = {
    "name": "write_file",
    "description": "Write content to a file. Creates dirs if needed. Can modify tools, identity, goals. CANNOT modify kernel/core.py.",
    "params": {
        "path": "File path relative to project root",
        "content": "Content to write",
    },
}

ROOT = Path(__file__).resolve().parent.parent
PROTECTED = [ROOT / "kernel" / "core.py"]


def execute(params: dict) -> str:
    rel_path = params.get("path", "")
    content = params.get("content", "")

    if not rel_path:
        return "No path specified."

    target = (ROOT / rel_path).resolve()

    # Safety: must be within project
    if not str(target).startswith(str(ROOT)):
        return "Access denied: outside project directory."

    # Protect kernel
    if target in PROTECTED:
        return "🧬 PROTECTED: kernel/core.py is your DNA. It cannot be modified."

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return f"✅ Written: {rel_path} ({len(content)} chars)"
