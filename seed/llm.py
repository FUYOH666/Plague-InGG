"""LLM client — OpenAI-compatible interface to local models."""

from __future__ import annotations

import json
import time
import httpx
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[dict] | None = None
    usage: dict = field(default_factory=dict)
    model: str = ""
    latency_ms: int = 0


class LLMClient:
    """Thin wrapper around OpenAI-compatible chat completions API."""

    def __init__(self, base_url: str, model: str = "", api_key: str = "not-needed", timeout: float = 120.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send chat completion request. Returns parsed response."""
        payload: dict = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.model:
            payload["model"] = self.model
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        t0 = time.monotonic()
        try:
            resp = self._client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise LLMError(f"HTTP {e.response.status_code}: {e.response.text[:500]}") from e
        except httpx.ConnectError as e:
            raise LLMError(f"Connection failed: {self.base_url}") from e

        latency_ms = int((time.monotonic() - t0) * 1000)
        data = resp.json()

        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        # Parse tool calls
        raw_tool_calls = message.get("tool_calls")
        tool_calls = None
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                args_str = fn.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {"_raw": args_str}
                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "arguments": args,
                })

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=data.get("usage", {}),
            model=data.get("model", self.model),
            latency_ms=latency_ms,
        )

    def health_check(self) -> bool:
        """Check if the LLM endpoint is reachable."""
        try:
            resp = self._client.get(f"{self.base_url}/models", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def close(self):
        self._client.close()


class LLMError(Exception):
    """Raised when LLM request fails."""
