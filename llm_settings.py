"""
OpenAI-compatible LLM endpoint resolution (local / remote LLM service, OpenRouter, etc.).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

import httpx

DEFAULT_LOCAL_BASE = "http://localhost:1234/v1"
DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "openai/gpt-5.4-nano"

# Treat as missing API key for cloud providers (must not be committed as real secrets)
_OPENROUTER_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "not-needed",
        "your-openrouter-api-key",
        "your-openrouter-api-key-here",
    }
)


def _env_get(environ: Mapping[str, str], key: str, default: str | None = None) -> str | None:
    v = environ.get(key)
    if v is None:
        return default
    s = v.strip()
    return default if s == "" else s


def normalize_llm_base_url(raw: str) -> str:
    """Ensure base URL ends with an OpenAI-compatible .../v1 segment."""
    t = raw.strip().rstrip("/")
    if "/v1" not in t:
        return f"{t}/v1"
    return t


def parse_llm_provider(environ: Mapping[str, str]) -> str:
    raw = (_env_get(environ, "LLM_PROVIDER") or "local").lower()
    if raw == "local":
        return "local"
    if raw == "openrouter":
        return "openrouter"
    raise ValueError(
        f"Unknown LLM_PROVIDER={raw!r}; use 'local' or 'openrouter'."
    )


def resolve_raw_base_url(environ: Mapping[str, str], provider: str) -> str:
    if provider == "openrouter":
        return _env_get(environ, "LLM_BASE_URL") or DEFAULT_OPENROUTER_BASE
    return (
        _env_get(environ, "LOCAL_AI_LLM_BASE_URL")
        or _env_get(environ, "LLM_BASE_URL")
        or DEFAULT_LOCAL_BASE
    )


def resolve_llm_model(environ: Mapping[str, str], provider: str) -> str:
    explicit = _env_get(environ, "LLM_MODEL")
    if explicit:
        return explicit
    if provider == "openrouter":
        return DEFAULT_OPENROUTER_MODEL
    return "default"


def build_llm_request_headers(
    provider: str, api_key: str, environ: Mapping[str, str]
) -> dict[str, str]:
    headers: dict[str, str] = {"Authorization": f"Bearer {api_key}"}
    if provider != "openrouter":
        return headers
    referer = _env_get(environ, "OPENROUTER_HTTP_REFERER")
    title = _env_get(environ, "OPENROUTER_APP_TITLE")
    if referer:
        headers["HTTP-Referer"] = referer
    if title:
        headers["X-Title"] = title
    return headers


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    api_key: str
    max_tokens: int
    temperature: float
    timeout: float
    request_headers: dict[str, str]


def load_llm_settings(environ: Mapping[str, str] | None = None) -> LLMSettings:
    env: Mapping[str, str] = os.environ if environ is None else environ
    provider = parse_llm_provider(env)
    raw_base = resolve_raw_base_url(env, provider)
    base_url = normalize_llm_base_url(raw_base)
    model = resolve_llm_model(env, provider)
    api_key = _env_get(env, "LLM_API_KEY") or "not-needed"

    if provider == "openrouter":
        k = api_key.strip()
        if not k or k.lower() in {p.lower() for p in _OPENROUTER_PLACEHOLDER_KEYS if p}:
            raise ValueError(
                "OpenRouter requires a real API key: set LLM_API_KEY "
                "(create a key at https://openrouter.ai/keys)."
            )

    max_tokens = int(_env_get(env, "LLM_MAX_TOKENS", "4096"))
    temperature = float(_env_get(env, "LLM_TEMPERATURE", "0.7"))
    timeout = float(_env_get(env, "LLM_TIMEOUT", "120"))
    headers = build_llm_request_headers(provider, api_key, env)

    return LLMSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        request_headers=headers,
    )


def post_chat_completion(settings: LLMSettings, messages: list) -> str:
    """POST /v1/chat/completions and return assistant message text."""
    response = httpx.post(
        f"{settings.base_url}/chat/completions",
        json={
            "model": settings.model,
            "messages": messages,
            "max_tokens": settings.max_tokens,
            "temperature": settings.temperature,
        },
        headers=settings.request_headers,
        timeout=settings.timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
