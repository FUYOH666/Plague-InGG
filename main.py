"""
Plague-InGG — Entry Point

Connects the kernel to any OpenAI-compatible LLM.
This file CAN be modified by the agent (unlike kernel/core.py).
"""

import logging
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

from llm_settings import LLMSettings, load_llm_settings, post_chat_completion

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

try:
    _SETTINGS: LLMSettings = load_llm_settings()
except ValueError as e:
    logger.error("LLM configuration error: %s", e)
    raise SystemExit(1) from e


def llm_call(messages: list) -> str:
    """Call OpenAI-compatible LLM API (local LLM service, OpenRouter, llama.cpp, etc.)."""
    try:
        return post_chat_completion(_SETTINGS, messages)
    except httpx.HTTPStatusError as e:
        logger.error(
            "LLM HTTP error: %s %s",
            e.response.status_code,
            e.response.text[:500] if e.response.text else "",
        )
        raise
    except httpx.RequestError as e:
        logger.error("LLM request failed: %s", e)
        raise


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from kernel.core import repl

    repl(llm_call)
