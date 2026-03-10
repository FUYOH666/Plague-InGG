#!/usr/bin/env python3
"""Pre-launch check: verify all components work together before running the agent.
Runs: router health, BGE, pytest, capability_benchmark, index_recall, optional smoke loop."""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

CHECKS: list[tuple[str, str, callable]] = []


def _register(name: str, desc: str):
    def decorator(fn):
        CHECKS.append((name, desc, fn))
        return fn

    return decorator


@_register("router", "LLM router (80B + 35B)")
def check_router() -> tuple[bool, str]:
    try:
        from router import ModelRouter

        r = ModelRouter()
        status = r.status()
        r.close()
        healthy = [s for s in status if s.get("healthy")]
        if not healthy:
            return False, "No LLM providers available"
        names = ", ".join(s["name"] for s in healthy)
        return True, f"{len(healthy)} OK: {names}"
    except Exception as e:
        return False, str(e)


@_register("bge_embedding", "BGE Embedding")
def check_bge_embedding() -> tuple[bool, str]:
    import httpx

    url = os.getenv("LOCAL_AI_EMBEDDING_BASE_URL") or "http://localhost:9001"
    try:
        r = httpx.get(f"{url.rstrip('/')}/healthz", timeout=5)
        return r.status_code == 200, f"{r.status_code}"
    except Exception as e:
        return False, str(e)


@_register("bge_reranker", "BGE Reranker")
def check_bge_reranker() -> tuple[bool, str]:
    import httpx

    url = os.getenv("LOCAL_AI_RERANKER_BASE_URL") or "http://localhost:9002"
    try:
        r = httpx.get(f"{url.rstrip('/')}/healthz", timeout=5)
        return r.status_code == 200, f"{r.status_code}"
    except Exception as e:
        return False, str(e)


@_register("pytest", "Unit tests")
def check_pytest() -> tuple[bool, str]:
    import subprocess

    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "seed/tests/", "-q", "--tb=no"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        out = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            m = [x for x in out.split() if x.isdigit()]
            return True, f"{m[-1] if m else '?'} passed"
        return False, out[-200:] if len(out) > 200 else out
    except Exception as e:
        return False, str(e)


@_register("capability_benchmark", "Capability gate")
def check_capability() -> tuple[bool, str]:
    import subprocess

    try:
        r = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "capability_benchmark.py")],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=90,
        )
        out = r.stdout or ""
        if "Result:" in out and "passed" in out:
            import re

            m = re.search(r"Result:\s*(\d+)/(\d+)\s+passed", out)
            if m and int(m.group(1)) == int(m.group(2)):
                return True, "all passed"
        return False, out[-150:] if len(out) > 150 else out
    except Exception as e:
        return False, str(e)


@_register("index_recall", "Recall indexing")
def check_index_recall() -> tuple[bool, str]:
    try:
        from rag import recall_search

        r = recall_search("test", top_n=1, max_chars=100)
        return True, "recall OK" if r is not None else "empty"
    except Exception as e:
        return False, str(e)


@_register("smoke_loop", "Minimal loop (привет)")
def check_smoke_loop() -> tuple[bool, str]:
    try:
        from router import ModelRouter
        from loop import run_loop

        router = ModelRouter()
        result = run_loop(
            router=router,
            system_prompt="Ты тестовый агент. Отвечай кратко.",
            user_message="Скажи только: ок",
            max_rounds=2,
            verbose=False,
        )
        router.close()
        if result and len(result.strip()) > 0:
            return True, f"got {len(result)} chars"
        return False, "empty response"
    except Exception as e:
        return False, str(e)


def main() -> int:
    smoke = "--smoke" in sys.argv
    print("Pre-launch check\n" + "=" * 50)

    failed = []
    for name, desc, fn in CHECKS:
        if name == "smoke_loop" and not smoke:
            continue
        ok, msg = fn()
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {desc}: {msg}")
        if not ok:
            failed.append(name)

    print("=" * 50)
    if failed:
        print(f"Failed: {', '.join(failed)}")
        print("Run with --smoke to include minimal loop test (requires LLM)")
        return 1
    print("All checks passed. Ready to launch.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
