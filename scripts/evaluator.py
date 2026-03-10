#!/usr/bin/env python3
"""Evaluator: single source of truth. Runs pytest + capability_benchmark, writes structured eval_result.json."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(os.getenv("EKATERINA_PROJECT_ROOT", "")) or Path(__file__).resolve().parent.parent
EVAL_OUTPUT = PROJECT_ROOT / "data" / "runner" / "eval_result.json"


def _run_pytest() -> tuple[str, str, int]:
    """Run pytest via runner. Returns (status, output, exit_code)."""
    runner = PROJECT_ROOT / "scripts" / "run_tests_runner.py"
    env = os.environ.copy()
    env["EKATERINA_PROJECT_ROOT"] = str(PROJECT_ROOT)
    try:
        result = subprocess.run(
            [sys.executable, str(runner), "seed/tests/"],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=130,
        )
        data_path = PROJECT_ROOT / "data" / "runner" / "last_test_result.json"
        if data_path.exists():
            data = json.loads(data_path.read_text(encoding="utf-8"))
            status = data.get("status", "UNKNOWN")
            output = data.get("output", "")
            return status, output, data.get("exit_code", result.returncode)
        return "UNKNOWN", "", result.returncode
    except subprocess.TimeoutExpired:
        return "FAILED", "Runner timed out", 1
    except Exception as e:
        return "FAILED", str(e), 1


def _run_capability_benchmark() -> tuple[int, int, list[str]]:
    """Run capability_benchmark. Returns (passed, total, failed_names)."""
    bench = PROJECT_ROOT / "scripts" / "capability_benchmark.py"
    try:
        result = subprocess.run(
            [sys.executable, str(bench)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        stdout = result.stdout or ""
        # Parse "Result: N/6 passed" or "Result: X/6 passed"
        m = re.search(r"Result:\s*(\d+)/(\d+)\s+passed", stdout)
        if m:
            passed = int(m.group(1))
            total = int(m.group(2))
        else:
            passed = 0
            total = 6

        failed = []
        for line in stdout.splitlines():
            if "[FAIL]" in line:
                parts = line.split(":", 1)
                if len(parts) >= 1:
                    failed.append(parts[0].strip().replace("[FAIL]", "").strip())

        return passed, total, failed
    except subprocess.TimeoutExpired:
        return 0, 6, ["timeout"]
    except Exception as e:
        return 0, 6, [str(e)]


def main() -> None:
    pytest_status, pytest_output, pytest_exit = _run_pytest()
    cap_passed, cap_total, cap_failed = _run_capability_benchmark()

    payload = {
        "pytest": pytest_status,
        "pytest_exit_code": pytest_exit,
        "pytest_output_preview": pytest_output[:500] if pytest_output else "",
        "capability": f"{cap_passed}/{cap_total}",
        "capability_passed": cap_passed,
        "capability_total": cap_total,
        "capability_failed": cap_failed,
        "details": {
            "pytest": pytest_status,
            "capability": cap_passed,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    EVAL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    EVAL_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Evaluator: pytest={pytest_status}, capability={cap_passed}/{cap_total}")
    if cap_failed:
        print(f"  Failed: {cap_failed}")
    sys.exit(0 if pytest_status == "PASSED" and cap_passed == cap_total else 1)


if __name__ == "__main__":
    main()
