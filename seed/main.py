#!/usr/bin/env python3
"""Ekaterina v2 — Seed. The minimum from which everything grows."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Ensure seed/ is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from router import ModelRouter
from loop import run_loop
from metrics import MetricsMonitor


def load_system_prompt() -> str:
    """Load system prompt from ENTRY.md (Variant C: minimal entry point)."""
    seed_dir = Path(__file__).resolve().parent
    prompt_path = seed_dir / "prompts" / "ENTRY.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


def main():
    """Interactive CLI loop."""
    print("=" * 60, file=sys.stderr)
    print("  Ekaterina v2 — Seed", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # Initialize router with two brains
    router = ModelRouter()
    
    # Initialize metrics monitor
    metrics = MetricsMonitor()
    metrics.load_metrics()
    start_time = time.time()

    # Check health
    status = router.status()
    for s in status:
        health = "OK" if s["healthy"] else "DOWN"
        print(f"  [{health}] {s['name']}", file=sys.stderr)
        metrics.record_latency(s['name'], 0)

    healthy_count = sum(1 for s in status if s["healthy"])
    if healthy_count == 0:
        print("\n  [!] No LLM providers available. Set LOCAL_AI_LLM_BASE_URL, LOCAL_AI_LLM_SECONDARY_BASE_URL in .env", file=sys.stderr)
        sys.exit(1)

    print(f"\n  {healthy_count} provider(s) ready.", file=sys.stderr)
    print("  Type your message. Empty line to exit.\n", file=sys.stderr)

    system_prompt = load_system_prompt()

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[bye]", file=sys.stderr)
            break

        if not user_input:
            break

        try:
            round_start = time.time()
            response = run_loop(
                router=router,
                system_prompt=system_prompt,
                user_message=user_input,
                max_rounds=int(os.getenv("MAX_ROUNDS", "0")),
                verbose=True,
            )
            duration = (time.time() - round_start) * 1000
            metrics.record_tool_call("run_loop", True, duration)
            print(f"\nagent> {response}\n")
        except Exception as e:
            metrics.record_error("main_loop", "exception", str(e))
            print(f"\n[ERROR] {e}\n", file=sys.stderr)

    # Save final metrics
    metrics.save_metrics()
    summary = metrics.get_metrics_summary()
    print(f"\n[Metrics] Uptime: {summary['uptime_hours']:.1f}h | Avg latency: {summary['average_latency_ms']:.0f}ms | Error rate: {summary['error_rate_percent']:.1f}%", file=sys.stderr)

    router.close()


if __name__ == "__main__":
    main()
