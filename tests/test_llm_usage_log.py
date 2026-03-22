"""LLM usage JSONL logging."""

import json
from unittest.mock import MagicMock


import llm_settings
from llm_settings import LLMSettings, post_chat_completion


def test_post_chat_completion_logs_usage(tmp_path, monkeypatch):
    logf = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(llm_settings, "_LLM_USAGE_LOG", logf)
    monkeypatch.setenv("LLM_LOG_USAGE", "1")

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
    }
    monkeypatch.setattr(llm_settings.httpx, "post", MagicMock(return_value=resp))

    settings = LLMSettings(
        provider="openrouter",
        base_url="https://example.com/v1",
        model="openai/test",
        api_key="k",
        max_tokens=100,
        temperature=0.5,
        timeout=30.0,
        request_headers={"Authorization": "Bearer k"},
    )
    out = post_chat_completion(settings, [{"role": "user", "content": "x"}])
    assert out == "hi"
    lines = logf.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["model"] == "openai/test"
    assert row["usage"]["total_tokens"] == 12


def test_post_chat_completion_skips_usage_when_disabled(tmp_path, monkeypatch):
    logf = tmp_path / "llm_usage.jsonl"
    monkeypatch.setattr(llm_settings, "_LLM_USAGE_LOG", logf)
    monkeypatch.setenv("LLM_LOG_USAGE", "0")

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "choices": [{"message": {"content": "x"}}],
        "usage": {"total_tokens": 5},
    }
    monkeypatch.setattr(llm_settings.httpx, "post", MagicMock(return_value=resp))
    settings = LLMSettings(
        provider="local",
        base_url="http://localhost/v1",
        model="m",
        api_key="k",
        max_tokens=10,
        temperature=0.0,
        timeout=1.0,
        request_headers={},
    )
    post_chat_completion(settings, [])
    assert not logf.exists()
