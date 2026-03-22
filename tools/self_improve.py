"""
Self-improvement cycle. The agent's evolution engine.
Branch → Hypothesis → Mutate → Test → Keep/Revert → Log.
"""

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

TOOL_SPEC = {
    "name": "self_improve",
    "description": "Run a self-improvement cycle. State a hypothesis about what to improve and why. The system will branch, let you make changes, test, and keep or revert.",
    "params": {
        "hypothesis": "What you think will improve and why",
        "action": "start|test|commit|revert (lifecycle of one improvement)",
        "branch": "Optional evolve-* branch name; defaults to evolution/.active_evolve_branch from last start",
    },
}

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_DIR = ROOT / "evolution"


def _active_branch_path() -> Path:
    return EVOLUTION_DIR / ".active_evolve_branch"


def _integration_branch(cwd: Path) -> str:
    for name in ("main", "master"):
        r = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{name}"],
            cwd=str(cwd),
            capture_output=True,
        )
        if r.returncode == 0:
            return name
    return "main"


def _current_git_branch(cwd: Path) -> str | None:
    r = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    if r.returncode != 0:
        logger.warning("git branch --show-current failed: %s", r.stderr.strip())
        return None
    out = r.stdout.strip()
    return out or None


def _resolve_branch(params: dict) -> tuple[str | None, str | None]:
    b = (params.get("branch") or "").strip()
    if b:
        return b, None
    p = _active_branch_path()
    if p.exists():
        name = p.read_text(encoding="utf-8").strip()
        if name:
            return name, None
    return None, (
        "No active evolve branch. Run action=start first, or pass branch= with the evolve-* name."
    )


def _set_marker(branch: str) -> None:
    EVOLUTION_DIR.mkdir(parents=True, exist_ok=True)
    _active_branch_path().write_text(branch, encoding="utf-8")


def _clear_marker() -> None:
    _active_branch_path().unlink(missing_ok=True)


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def execute(params: dict) -> str:
    hypothesis = params.get("hypothesis", "")
    action = params.get("action", "start")

    if action == "start":
        if not hypothesis:
            return "Need a hypothesis to start improvement cycle."
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        branch = f"evolve-{ts}"
        r = _run_git(["git", "checkout", "-b", branch], ROOT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            logger.warning("git checkout -b failed: %s", err)
            return f"Git branch failed: {err or 'unknown error'}"
        _set_marker(branch)
        _log({"type": "improve_start", "hypothesis": hypothesis, "branch": branch})
        return f"🧬 Evolution branch '{branch}' created. Make your changes, then use action='test'."

    if action == "test":
        branch, err = _resolve_branch(params)
        if err:
            return err
        cur = _current_git_branch(ROOT)
        if cur != branch:
            return (
                f"Must be on evolve branch {branch!r} (currently {cur!r}). "
                "Checkout that branch or pass branch= explicitly."
            )
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
        )
        passed = r.returncode == 0
        out = (r.stdout or "") + (r.stderr or "")
        _log({"type": "improve_test", "passed": passed, "output": out[-500:]})
        if passed:
            return "✅ Tests passed. Use action='commit' to keep or action='revert' to discard."
        return f"❌ Tests failed:\n{out[-1000:]}\nUse action='revert' to discard."

    if action == "commit":
        branch, err = _resolve_branch(params)
        if err:
            return err
        cur = _current_git_branch(ROOT)
        if cur != branch:
            return (
                f"Must be on evolve branch {branch!r} (currently {cur!r}) to commit. "
                "Checkout the evolve branch first."
            )
        ib = _integration_branch(ROOT)

        r = _run_git(["git", "add", "-A"], ROOT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            logger.warning("git add failed: %s", err)
            return f"git add failed: {err or 'unknown error'}"

        r = _run_git(
            ["git", "commit", "-m", f"evolve: {hypothesis[:80]}"],
            ROOT,
        )
        if r.returncode != 0:
            combined = (r.stdout or "") + (r.stderr or "")
            if "nothing to commit" in combined.lower():
                return "Nothing to commit. Make changes on the evolve branch first."
            logger.warning("git commit failed: %s", combined.strip())
            return f"Commit failed: {combined.strip() or 'unknown error'}"

        r = _run_git(["git", "checkout", ib], ROOT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            logger.warning("git checkout %s failed: %s", ib, err)
            return f"checkout {ib} failed: {err or 'unknown error'}"

        merge_msg = f"Merge {branch}: {hypothesis[:60]}"
        r = _run_git(["git", "merge", "--no-ff", branch, "-m", merge_msg], ROOT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            logger.warning("git merge failed: %s", err)
            return (
                f"Merge failed (you may be on {ib} with conflicts): {err or 'unknown error'}\n"
                "Resolve manually or checkout the evolve branch and use action=revert."
            )

        dr = _run_git(["git", "branch", "-d", branch], ROOT)
        if dr.returncode != 0:
            logger.warning("git branch -d %s: %s", branch, (dr.stderr or "").strip())

        _clear_marker()
        _log({"type": "improve_commit", "hypothesis": hypothesis, "branch": branch})
        return f"🌿 Evolution committed and merged to {ib}: {hypothesis[:80]}"

    if action == "revert":
        branch, err = _resolve_branch(params)
        if err:
            return err
        ib = _integration_branch(ROOT)

        r = _run_git(["git", "checkout", "-f", ib], ROOT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            logger.warning("git checkout -f %s failed: %s", ib, err)
            return f"checkout {ib} failed: {err or 'unknown error'}"

        dr = _run_git(["git", "branch", "-D", branch], ROOT)
        if dr.returncode != 0 and "not found" not in (dr.stderr or "").lower():
            logger.warning("git branch -D %s: %s", branch, (dr.stderr or "").strip())

        _clear_marker()
        _log({"type": "improve_revert", "hypothesis": hypothesis, "branch": branch})
        return f"🔄 Reverted to {ib} and removed branch {branch!r} (if it existed)."

    return f"Unknown action: {action}"


def _log(entry: dict):
    EVOLUTION_DIR.mkdir(exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(EVOLUTION_DIR / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
