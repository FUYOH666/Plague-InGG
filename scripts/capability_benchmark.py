#!/usr/bin/env python3
"""Capability-gate: benchmark agent capabilities. Beyond unit tests — verifies agent can do typical tasks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "seed"))


def check_run_tests() -> tuple[bool, str]:
    """Correctness-gate: unit tests pass."""
    from tools import run_tests
    result = run_tests("seed/tests/")
    passed = "[PASSED]" in result
    return passed, result[:200]


def check_read_file() -> tuple[bool, str]:
    """Can read project files."""
    from tools import read_file
    try:
        content = read_file("README.md")
        return len(content) > 10, f"read {len(content)} chars"
    except Exception as e:
        return False, str(e)


def check_evolution_log() -> tuple[bool, str]:
    """Evolution log exists and is writable."""
    from tools import evolution_log
    try:
        evolution_log("read")
        evolution_log("append", "capability_benchmark check")
        return True, "evolution_log OK"
    except Exception as e:
        return False, str(e)


def check_rag_index() -> tuple[bool, str]:
    """RAG indexing works."""
    from tools import rag_index
    try:
        # Index a small file
        (PROJECT_ROOT / "data" / "memory" / "knowledge").mkdir(parents=True, exist_ok=True)
        test_file = PROJECT_ROOT / "data" / "memory" / "knowledge" / "_cap_bench.md"
        test_file.write_text("# capability benchmark\n\nTest content for RAG.", encoding="utf-8")
        r = rag_index("data/memory/knowledge/_cap_bench.md")
        return "OK" in r or "indexed" in r.lower(), r[:100]
    except Exception as e:
        return False, str(e)


def check_rag_search() -> tuple[bool, str]:
    """RAG search works (if indexed)."""
    from tools import rag_search
    try:
        r = rag_search("capability benchmark", top_k=2)
        return not r.startswith("[ERROR]") and ("capability" in r.lower() or "empty" in r.lower()), r[:150]
    except Exception as e:
        return False, str(e)


def check_safe_edit_rollback() -> tuple[bool, str]:
    """safe_edit rolls back when tests fail."""
    from tools import read_file, safe_edit
    path = "seed/tests/test_capability_benchmark.py"
    try:
        content = read_file(path)
        old = "assert True"
        new = "assert False  # cap_bench"
        if old not in content:
            return False, "Anchor not found"
        r = safe_edit(path, old, new)
        if "ROLLBACK" in r or "rollback" in r.lower():
            return True, "rollback worked"
        return False, r[:150]
    except Exception as e:
        return False, str(e)


BENCHMARKS = [
    ("run_tests", "Unit tests pass", check_run_tests),
    ("read_file", "Can read files", check_read_file),
    ("evolution_log", "Evolution log works", check_evolution_log),
    ("rag_index", "RAG indexing works", check_rag_index),
    ("rag_search", "RAG search works", check_rag_search),
    ("safe_edit_rollback", "safe_edit rollback on fail", check_safe_edit_rollback),
]


def main() -> None:
    print("Capability-gate benchmark\n" + "=" * 40)
    passed = 0
    failed = []
    for name, desc, check_fn in BENCHMARKS:
        try:
            ok, msg = check_fn()
            if ok:
                print(f"  [PASS] {name}: {desc}")
                passed += 1
            else:
                print(f"  [FAIL] {name}: {msg[:80]}")
                failed.append((name, msg))
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            failed.append((name, str(e)))

    print("=" * 40)
    print(f"Result: {passed}/{len(BENCHMARKS)} passed")
    if failed:
        print("\nFailed:")
        for name, msg in failed:
            print(f"  - {name}: {msg[:100]}")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
