#!/usr/bin/env python3
"""Self-test: run pytest, revert last commit on failure, log to evolution_log."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "seed"))


def run_tests() -> tuple[bool, str]:
    """Run pytest via runner. Returns (passed, output)."""
    runner_path = PROJECT_ROOT / "scripts" / "run_tests_runner.py"
    result_path = PROJECT_ROOT / "data" / "runner" / "last_test_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, str(runner_path), "seed/tests/"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=130,
        )
        if not result_path.exists():
            return False, "Runner did not produce result"
        import json
        data = json.loads(result_path.read_text(encoding="utf-8"))
        return data.get("status") == "PASSED", data.get("output", "")
    except Exception as e:
        return False, str(e)


def evolution_log_append(content: str) -> None:
    """Append to evolution-log.md."""
    log_path = PROJECT_ROOT / "data" / "memory" / "evolution-log.md"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    block = f"\n## {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{content}\n"
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    log_path.write_text(existing + block, encoding="utf-8")


def main() -> None:
    passed, output = run_tests()
    if passed:
        print("[PASSED]")
        print(output)
        sys.exit(0)

    print("[FAILED]")
    print(output)

    # Check if git repo and we can revert
    git_dir = PROJECT_ROOT / ".git"
    if not git_dir.exists():
        evolution_log_append(f"self_test FAILED (no git): {output[:500]}")
        sys.exit(1)

    # Check if there are commits
    result = subprocess.run(
        ["git", "rev-list", "-n", "1", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        evolution_log_append(f"self_test FAILED (no commits to revert): {output[:500]}")
        sys.exit(1)

    # Revert last commit
    revert_result = subprocess.run(
        ["git", "revert", "HEAD", "--no-edit"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if revert_result.returncode == 0:
        evolution_log_append(
            f"self_test FAILED → git revert HEAD. Output: {output[:400]}"
        )
        print("\n[REVERTED] Last commit reverted.")
    else:
        evolution_log_append(
            f"self_test FAILED, revert failed: {revert_result.stderr}. Test output: {output[:300]}"
        )

    sys.exit(1)


if __name__ == "__main__":
    main()
