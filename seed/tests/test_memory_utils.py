"""Tests for memory_utils — salience, forgetting curves."""

import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import memory_utils as mu


class TestSalience:
    def test_salience_no_timestamp(self):
        assert mu.salience(last_accessed_ts=None) == 1.0

    def test_salience_recent(self):
        now = __import__("time").time()
        assert mu.salience(last_accessed_ts=now, base_importance=1.0) > 0.99

    def test_salience_decay(self):
        now = __import__("time").time()
        week_ago = now - 7 * 86400
        recent = mu.salience(last_accessed_ts=now, decay_factor=0.99)
        old = mu.salience(last_accessed_ts=week_ago, decay_factor=0.99)
        assert recent > old


class TestFilterBySalience:
    def test_filter_keeps_recent(self):
        now = __import__("time").time()
        items = [
            {"content": "new", "timestamp": now, "importance": 1.0},
            {"content": "old", "timestamp": now - 30 * 86400, "importance": 0.5},
        ]
        filtered = mu.filter_by_salience(items, threshold=0.1)
        assert len(filtered) >= 1
        assert any("new" in f["content"] for f in filtered)

    def test_filter_sorts_by_salience(self):
        now = __import__("time").time()
        items = [
            {"content": "a", "timestamp": now - 10 * 86400},
            {"content": "b", "timestamp": now},
        ]
        filtered = mu.filter_by_salience(items, threshold=0.01)
        assert len(filtered) == 2
        assert filtered[0]["content"] == "b"


class TestFilterMemoryBySalience:
    def test_parse_and_filter(self):
        text = """## 2026-03-01 10:00 — Old
Content from a month ago.

## 2026-03-09 12:00 — Recent
Content from today.
"""
        result = mu.filter_memory_by_salience(text, max_chars=5000)
        assert "Recent" in result or "Content from today" in result
