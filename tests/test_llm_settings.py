"""Unit tests for LLM URL/header resolution and chat completion client."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import llm_settings
from llm_settings import (
    LLMSettings,
    build_llm_request_headers,
    load_llm_settings,
    normalize_llm_base_url,
    parse_llm_provider,
    post_chat_completion,
    resolve_llm_model,
    resolve_raw_base_url,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("http://localhost:1234", "http://localhost:1234/v1"),
        ("http://localhost:1234/", "http://localhost:1234/v1"),
        ("http://x:8005", "http://x:8005/v1"),
        ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
        ("https://openrouter.ai/api/v1/", "https://openrouter.ai/api/v1"),
    ],
)
def test_normalize_llm_base_url(raw, expected):
    assert normalize_llm_base_url(raw) == expected


def test_parse_llm_provider_variants():
    assert parse_llm_provider({"LLM_PROVIDER": "local"}) == "local"
    assert parse_llm_provider({"LLM_PROVIDER": "openrouter"}) == "openrouter"
    assert parse_llm_provider({}) == "local"


def test_parse_llm_provider_invalid():
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        parse_llm_provider({"LLM_PROVIDER": "other"})


def test_resolve_raw_base_url_local_precedence():
    env = {
        "LOCAL_AI_LLM_BASE_URL": "http://remote-llm/v1",
        "LLM_BASE_URL": "http://llm/v1",
    }
    assert resolve_raw_base_url(env, "local") == "http://remote-llm/v1"
    env2 = {"LLM_BASE_URL": "http://only/v1"}
    assert resolve_raw_base_url(env2, "local") == "http://only/v1"
    assert resolve_raw_base_url({}, "local") == "http://localhost:1234/v1"


def test_resolve_raw_base_url_openrouter():
    assert resolve_raw_base_url({}, "openrouter") == "https://openrouter.ai/api/v1"
    env = {"LLM_BASE_URL": "https://custom.example/v1"}
    assert resolve_raw_base_url(env, "openrouter") == "https://custom.example/v1"


def test_resolve_llm_model_defaults():
    assert resolve_llm_model({}, "local") == "default"
    assert resolve_llm_model({}, "openrouter") == "openai/gpt-5.4-nano"
    assert resolve_llm_model({"LLM_MODEL": "custom"}, "openrouter") == "custom"


def test_build_llm_request_headers_openrouter_optional():
    env = {
        "OPENROUTER_HTTP_REFERER": "https://example.com",
        "OPENROUTER_APP_TITLE": "PlagueTest",
    }
    h = build_llm_request_headers("openrouter", "sk-test", env)
    assert h["Authorization"] == "Bearer sk-test"
    assert h["HTTP-Referer"] == "https://example.com"
    assert h["X-Title"] == "PlagueTest"

    h2 = build_llm_request_headers("openrouter", "k", {})
    assert h2 == {"Authorization": "Bearer k"}


def test_load_llm_settings_openrouter_requires_real_key():
    with pytest.raises(ValueError, match="OpenRouter requires"):
        load_llm_settings(
            {
                "LLM_PROVIDER": "openrouter",
                "LLM_API_KEY": "not-needed",
            }
        )


def test_load_llm_settings_openrouter_ok():
    s = load_llm_settings(
        {
            "LLM_PROVIDER": "openrouter",
            "LLM_API_KEY": "sk-or-test-key-ok",
        }
    )
    assert s.provider == "openrouter"
    assert s.base_url == "https://openrouter.ai/api/v1"
    assert s.model == "openai/gpt-5.4-nano"
    assert "Authorization" in s.request_headers


def test_post_chat_completion_parses_response(monkeypatch):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": "assistant text"}}]}
    monkeypatch.setattr(llm_settings.httpx, "post", MagicMock(return_value=resp))

    settings = LLMSettings(
        provider="local",
        base_url="http://localhost:1234/v1",
        model="default",
        api_key="x",
        max_tokens=100,
        temperature=0.5,
        timeout=30.0,
        request_headers={"Authorization": "Bearer x"},
    )
    out = post_chat_completion(settings, [{"role": "user", "content": "hi"}])
    assert out == "assistant text"
    llm_settings.httpx.post.assert_called_once()
    call_kw = llm_settings.httpx.post.call_args.kwargs
    assert call_kw["json"]["model"] == "default"
    assert call_kw["headers"] == settings.request_headers
