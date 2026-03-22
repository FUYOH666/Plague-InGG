"""Write/overwrite a file. The agent's hands. Enables self-modification."""

import os
from pathlib import Path

TOOL_SPEC = {
    "name": "write_file",
    "description": (
        "Write content to a file. Creates dirs if needed. CANNOT modify kernel/core.py. "
        "Optional shrink guard: WRITE_FILE_SHRINK_GUARD=1 refuses if new text is much shorter "
        "than existing (see WRITE_FILE_MIN_RATIO). Prefer str_replace_file for small edits."
    ),
    "params": {
        "path": "File path relative to project root",
        "content": "Content to write",
    },
}

ROOT = Path(__file__).resolve().parent.parent
PROTECTED = [ROOT / "kernel" / "core.py"]


def _env_truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


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

    if target.is_file() and _env_truthy("WRITE_FILE_SHRINK_GUARD"):
        old = target.read_text(encoding="utf-8")
        min_len = int(os.getenv("WRITE_FILE_MIN_LEN", "200"))
        if len(old) >= min_len:
            ratio = float(os.getenv("WRITE_FILE_MIN_RATIO", "0.35"))
            if len(content) < len(old) * ratio:
                return (
                    f"❌ Shrink guard: new size {len(content)} < {ratio:.0%} of old {len(old)}. "
                    f"Use str_replace_file or disable WRITE_FILE_SHRINK_GUARD."
                )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    return f"✅ Written: {rel_path} ({len(content)} chars)"
