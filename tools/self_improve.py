"""
Self-improvement cycle. The agent's evolution engine.
Branch → Hypothesis → Mutate → Test → Keep/Revert → Log.
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

TOOL_SPEC = {
    "name": "self_improve",
    "description": "Run a self-improvement cycle. State a hypothesis about what to improve and why. The system will branch, let you make changes, test, and keep or revert.",
    "params": {
        "hypothesis": "What you think will improve and why",
        "action": "start|test|commit|revert (lifecycle of one improvement)",
    },
}

ROOT = Path(__file__).resolve().parent.parent
EVOLUTION_DIR = ROOT / "evolution"


def execute(params: dict) -> str:
    hypothesis = params.get("hypothesis", "")
    action = params.get("action", "start")

    if action == "start":
        if not hypothesis:
            return "Need a hypothesis to start improvement cycle."
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        branch = f"evolve-{ts}"
        r = subprocess.run(["git", "checkout", "-b", branch], capture_output=True, text=True, cwd=str(ROOT))
        if r.returncode != 0:
            return f"Git branch failed: {r.stderr}"
        _log({"type": "improve_start", "hypothesis": hypothesis, "branch": branch})
        return f"🧬 Evolution branch '{branch}' created. Make your changes, then use action='test'."

    elif action == "test":
        r = subprocess.run(["python", "-m", "pytest", "--tb=short", "-q"], capture_output=True, text=True, timeout=60, cwd=str(ROOT))
        passed = r.returncode == 0
        _log({"type": "improve_test", "passed": passed, "output": r.stdout[-500:]})
        if passed:
            return "✅ Tests passed. Use action='commit' to keep or action='revert' to discard."
        else:
            return f"❌ Tests failed:\n{r.stdout[-1000:]}\nUse action='revert' to discard."

    elif action == "commit":
        r = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, cwd=str(ROOT))
        r = subprocess.run(["git", "commit", "-m", f"evolve: {hypothesis[:80]}"], capture_output=True, text=True, cwd=str(ROOT))
        subprocess.run(["git", "checkout", "main"], capture_output=True, text=True, cwd=str(ROOT))
        subprocess.run(["git", "merge", "--no-ff", "-"], capture_output=True, text=True, cwd=str(ROOT))
        _log({"type": "improve_commit", "hypothesis": hypothesis})
        return f"🌿 Evolution committed: {hypothesis[:80]}"

    elif action == "revert":
        subprocess.run(["git", "checkout", "main"], capture_output=True, text=True, cwd=str(ROOT))
        subprocess.run(["git", "branch", "-D", "-"], capture_output=True, text=True, cwd=str(ROOT))
        _log({"type": "improve_revert", "hypothesis": hypothesis})
        return "🔄 Reverted to main. Hypothesis did not improve the system."

    return f"Unknown action: {action}"


def _log(entry: dict):
    EVOLUTION_DIR.mkdir(exist_ok=True)
    entry["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(EVOLUTION_DIR / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
