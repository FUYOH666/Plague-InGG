"""Model Router — routes requests between two LLM backends with health-check and failover."""

from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field

from llm import LLMClient, LLMResponse, LLMError


def _env_url(key: str, default: str) -> str:
    """Read URL from env, ensure /v1 suffix for OpenAI-compatible API."""
    url = os.getenv(key) or default
    url = url.rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


@dataclass
class Provider:
    name: str
    base_url: str
    model: str = ""
    priority: int = 1
    api_key: str = "not-needed"
    timeout: float = 120.0
    # runtime state
    healthy: bool = True
    last_check: float = 0.0
    total_calls: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0


class ModelRouter:
    """Routes LLM requests to two backends: 35B (code) + 80B (review)."""

    # 35B — код, tool calls. 80B — рефлексия, ревью.
    # URLs from .env: LOCAL_AI_LLM_SECONDARY_BASE_URL, LOCAL_AI_LLM_BASE_URL
    DEFAULT_PROVIDERS = [
        Provider(
            name="llm_35b",
            base_url=_env_url("LOCAL_AI_LLM_SECONDARY_BASE_URL", "http://localhost:8005/v1"),
            model="",
            priority=1,
        ),
        Provider(
            name="llm_80b",
            base_url=_env_url("LOCAL_AI_LLM_BASE_URL", "http://localhost:1234/v1"),
            model="",
            priority=2,
        ),
    ]

    def __init__(self, providers: list[Provider] | None = None, check_interval: float = 30.0):
        self.providers = providers or [Provider(**p.__dict__) for p in self.DEFAULT_PROVIDERS]
        self._provider_by_name = {p.name: p for p in self.providers}
        self.check_interval = check_interval
        self._clients: dict[str, LLMClient] = {}
        self._lock = threading.Lock()

        # Initialize clients
        for p in self.providers:
            self._clients[p.name] = LLMClient(
                base_url=p.base_url,
                model=p.model,
                api_key=p.api_key,
                timeout=p.timeout,
            )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        task: str = "default",
        **kwargs,
    ) -> LLMResponse:
        """
        Route request. task='reflect' → 80B LLM for reflection/review.
        task='default' → 35B LLM for code and tool calls.
        """
        errors = []
        providers = self._providers_for_task(task)

        for provider in providers:
            if not self._is_healthy(provider):
                continue

            client = self._clients[provider.name]
            try:
                response = client.chat(messages, tools=tools, **kwargs)
                # Update stats
                provider.total_calls += 1
                provider.avg_latency_ms = (
                    provider.avg_latency_ms * 0.9 + response.latency_ms * 0.1
                )
                return response
            except LLMError as e:
                provider.total_errors += 1
                provider.healthy = False
                provider.last_check = time.monotonic()
                errors.append(f"{provider.name}: {e}")
                continue

        raise LLMError(
            f"All providers failed:\n" + "\n".join(errors) if errors
            else "No healthy providers available"
        )

    def status(self) -> list[dict]:
        """Return status of all providers."""
        result = []
        for p in self.providers:
            result.append({
                "name": p.name,
                "healthy": self._is_healthy(p),
                "priority": p.priority,
                "total_calls": p.total_calls,
                "total_errors": p.total_errors,
                "avg_latency_ms": round(p.avg_latency_ms),
            })
        return result

    def _providers_for_task(self, task: str) -> list[Provider]:
        """35B for code, 80B for reflection."""
        if task == "reflect":
            order = ["llm_80b", "llm_35b"]
        else:
            order = ["llm_35b", "llm_80b"]
        result = []
        for name in order:
            p = self._provider_by_name.get(name)
            if p:
                result.append(p)
        for p in self.providers:
            if p not in result:
                result.append(p)
        return result

    def _is_healthy(self, provider: Provider) -> bool:
        now = time.monotonic()
        if not provider.healthy and (now - provider.last_check) > self.check_interval:
            # Re-check
            client = self._clients[provider.name]
            provider.healthy = client.health_check()
            provider.last_check = now
        return provider.healthy

    def close(self):
        for client in self._clients.values():
            client.close()
