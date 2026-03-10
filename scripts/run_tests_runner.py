#!/usr/bin/env python3
"""Runner: executes tests in isolated process, writes immutable result to file. Source of truth for test results."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow override for tests (tmp_project)
PROJECT_ROOT = Path(os.getenv("EKATERINA_PROJECT_ROOT", "")) or Path(__file__).resolve().parent.parent
RUNNER_OUTPUT = PROJECT_ROOT / "data" / "runner" / "last_test_result.json"


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "seed/tests/"
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-v", "--tb=short", "--no-header"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout or ""
        if result.stderr:
            output += "\n" + result.stderr
        status = "PASSED" if result.returncode == 0 else "FAILED"
    except subprocess.TimeoutExpired:
        output = "Tests timed out after 120s"
        status = "FAILED"
        result = type("R", (), {"returncode": 1})()
    except Exception as e:
        output = str(e)
        status = "FAILED"
        result = type("R", (), {"returncode": 1})()

    RUNNER_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "exit_code": result.returncode,
        "output": output.strip(),
        "path": path,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    RUNNER_OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
