"""Execute shell commands. Use with care."""

import subprocess

TOOL_SPEC = {
    "name": "shell",
    "description": "Run a shell command. Returns stdout+stderr. Timeout 30s.",
    "params": {"command": "Shell command to execute"},
}


def execute(params: dict) -> str:
    cmd = params.get("command", "")
    if not cmd:
        return "No command."
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(__import__("pathlib").Path(__file__).resolve().parent.parent)
        )
        out = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        err = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
        return f"exit={result.returncode}\n{out}\n{err}".strip()
    except subprocess.TimeoutExpired:
        return "Command timed out (30s)."
    except Exception as e:
        return f"Error: {e}"
