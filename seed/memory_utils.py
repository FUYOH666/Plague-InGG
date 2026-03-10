"""Memory utilities — salience, forgetting curves (Blueprint)."""

from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Any


def _parse_md_sections_with_timestamps(text: str) -> list[dict[str, Any]]:
    """Parse markdown with ## YYYY-MM-DD HH:MM headers into items with timestamp."""
    items = []
    current = []
    current_ts = None
    for line in text.split("\n"):
        m = re.match(r"^##\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})", line)
        if m:
            if current:
                content = "\n".join(current).strip()
                if content:
                    items.append({
                        "content": content,
                        "timestamp": current_ts or datetime.now().isoformat(),
                        "importance": 1.0,
                    })
            current = [line]
            try:
                dt = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
                current_ts = dt.isoformat()
            except ValueError:
                current_ts = None
        else:
            current.append(line)
    if current:
        content = "\n".join(current).strip()
        if content:
            items.append({
                "content": content,
                "timestamp": current_ts or datetime.now().isoformat(),
                "importance": 1.0,
            })
    return items


def salience(
    last_accessed_ts: float | None = None,
    base_importance: float = 1.0,
    decay_factor: float | None = None,
) -> float:
    """Compute salience from last access time. Ebbinghaus-style decay."""
    decay = float(os.getenv("MEMORY_DECAY_FACTOR", "0.99")) if decay_factor is None else decay_factor
    if last_accessed_ts is None:
        return base_importance
    days = (time.time() - last_accessed_ts) / 86400
    return base_importance * (decay ** days)


def filter_by_salience(
    items: list[dict[str, Any]],
    threshold: float | None = None,
    timestamp_key: str = "timestamp",
    importance_key: str = "importance",
) -> list[dict[str, Any]]:
    """Filter items by salience threshold. Items need 'content', 'timestamp', optional 'importance'."""
    thresh = float(os.getenv("MEMORY_SALIENCE_THRESHOLD", "0.3")) if threshold is None else threshold
    now = time.time()
    result = []
    for item in items:
        ts = item.get(timestamp_key)
        if ts is None:
            ts = now
        elif isinstance(ts, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts = dt.timestamp()
            except (ValueError, TypeError):
                ts = now
        imp = item.get(importance_key, 1.0)
        s = salience(last_accessed_ts=ts, base_importance=imp)
        if s >= thresh:
            item["_salience"] = s
            result.append(item)
    result.sort(key=lambda x: x.get("_salience", 0), reverse=True)
    return result


def filter_memory_by_salience(text: str, max_chars: int = 16000) -> str:
    """Parse markdown sections, filter by salience, return concatenated text."""
    items = _parse_md_sections_with_timestamps(text)
    if not items:
        return text[-max_chars:] if len(text) > max_chars else text
    filtered = filter_by_salience(items)
    parts = [item["content"] for item in filtered]
    out = "\n\n".join(parts)
    return out[-max_chars:] if len(out) > max_chars else out
