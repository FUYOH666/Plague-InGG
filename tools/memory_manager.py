"""
Memory Manager Tool

Инструмент для управления иерархической памятью.
Обеспечивает долгосрочный доступ к знаниям через:
- Суммаризацию и сжатие записей
- Архивацию старых записей в memory/archive.json
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

TOOL_SPEC = {
    "name": "memory_manager",
    "description": "Manage hierarchical memory: status, summarize (compress stream into archive), archive (move old records), hierarchy (show structure). Use summarize when stream.md grows large.",
    "params": {
        "action": "status|summarize|archive|hierarchy",
        "content": "Content to summarize (optional, for summarize action)",
        "threshold_date": "YYYY-MM-DD for archive (optional)",
    },
}

ROOT = Path(__file__).resolve().parent.parent
MEMORY_FILE = ROOT / "memory" / "stream.md"
ARCHIVE_FILE = ROOT / "memory" / "archive.json"
KEEP_STREAM_CHARS = 2000


def _load_archive() -> dict:
    """Load archive from disk."""
    if not ARCHIVE_FILE.exists():
        return {"archived": [], "last_summary": "", "updated": None}
    try:
        return json.loads(ARCHIVE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"archived": [], "last_summary": "", "updated": None}


def _save_archive(data: dict) -> None:
    """Save archive to disk."""
    ARCHIVE_FILE.parent.mkdir(exist_ok=True)
    data["updated"] = datetime.now(timezone.utc).isoformat()
    ARCHIVE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _parse_stream_sections(text: str) -> tuple[str, list[dict]]:
    """Parse stream.md into preamble and sections with date and content."""
    preamble_lines = []
    sections = []
    current = None
    for line in text.split("\n"):
        if m := re.match(r"^## (\d{4}-\d{2}-\d{2})", line):
            if current:
                sections.append(current)
            current = {"date": m.group(1), "header": line, "content": []}
        elif current is not None:
            current["content"].append(line)
        else:
            preamble_lines.append(line)
    if current:
        sections.append(current)
    preamble = "\n".join(preamble_lines).rstrip()
    return preamble, sections


def _section_to_text(s: dict) -> str:
    """Convert section dict to text."""
    return s["header"] + "\n" + "\n".join(s["content"])


def _summarize_section(s: dict, max_chars: int = 200) -> str:
    """Extract key summary from section (first N chars)."""
    full = _section_to_text(s)
    if len(full) <= max_chars:
        return full
    return full[:max_chars] + "..."


def execute(params: dict) -> str:
    """Execute memory_manager action. Returns string for kernel."""
    action = params.get("action", "status")
    threshold_date = params.get("threshold_date", "")

    if action == "status":
        stream_size = MEMORY_FILE.stat().st_size if MEMORY_FILE.exists() else 0
        archive_data = _load_archive()
        archive_count = len(archive_data.get("archived", []))
        return (
            f"Memory status: stream.md={stream_size} bytes, "
            f"archive={archive_count} records. Use action=summarize to compress."
        )

    elif action == "hierarchy":
        return """# Memory Hierarchy
## Short-term (stream.md)
- Current context, last ~2000 chars kept
- Fast access to recent entries

## Long-term (archive.json)
- Archived/summarized records
- Persisted on disk

## Mechanisms
1. summarize — compress stream, move old sections to archive
2. archive — move records older than threshold_date"""

    elif action == "summarize":
        if not MEMORY_FILE.exists():
            return "No stream.md to summarize."
        text = MEMORY_FILE.read_text(encoding="utf-8")
        if len(text) <= KEEP_STREAM_CHARS:
            return f"Stream is {len(text)} chars, under {KEEP_STREAM_CHARS}. No summarization needed."
        preamble, sections = _parse_stream_sections(text)
        if not sections:
            return "Could not parse stream sections."
        archive_data = _load_archive()
        to_archive = []
        to_keep = list(sections)
        while to_keep and sum(len(_section_to_text(s)) for s in to_keep) > KEEP_STREAM_CHARS:
            s = to_keep.pop(0)
            summary = _summarize_section(s)
            to_archive.append({"date": s["date"], "summary": summary})
        archive_data["archived"] = archive_data.get("archived", []) + to_archive
        archive_data["last_summary"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _save_archive(archive_data)
        kept_text = "\n\n".join(_section_to_text(s) for s in to_keep)
        if preamble:
            kept_text = preamble + "\n\n" + kept_text
        MEMORY_FILE.write_text(kept_text, encoding="utf-8")
        return f"Summarized: archived {len(to_archive)} sections. Stream now {len(kept_text)} chars."

    elif action == "archive":
        if not threshold_date:
            return "Need threshold_date (YYYY-MM-DD) for archive action."
        archive_data = _load_archive()
        existing = archive_data.get("archived", [])
        if MEMORY_FILE.exists():
            preamble, sections = _parse_stream_sections(MEMORY_FILE.read_text(encoding="utf-8"))
            for s in sections:
                if s["date"] < threshold_date:
                    existing.append({"date": s["date"], "summary": _summarize_section(s)})
            kept = [s for s in sections if s["date"] >= threshold_date]
            kept_text = "\n\n".join(_section_to_text(s) for s in kept)
            if preamble:
                kept_text = preamble + "\n\n" + kept_text
            MEMORY_FILE.write_text(kept_text, encoding="utf-8")
        archive_data["archived"] = existing
        _save_archive(archive_data)
        return f"Archived records before {threshold_date}. Archive now has {len(existing)} records."

    return f"Unknown action: {action}. Use status|summarize|archive|hierarchy."
