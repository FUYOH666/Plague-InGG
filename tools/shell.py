"""Execute shell commands. Use with care."""

import os
import re
import subprocess
from pathlib import Path

TOOL_SPEC = {
    "name": "shell",
    "description": (
        "Run a shell command. Returns stdout+stderr. Timeout 30s. "
        "Policy: SHELL_POLICY=deny (default) blocks risky patterns; "
        "strict = only commands starting with SHELL_ALLOW_PREFIXES; "
        "off = no checks."
    ),
    "params": {"command": "Shell command to execute"},
}

ROOT = Path(__file__).resolve().parent.parent

# Deny if normalized command contains any of these (lowercased substring match)
_DENY_SUBSTRINGS = (
    "mkfs.",
    "dd if=",
    ":(){",
    ">/dev/sd",
    ">/dev/nvme",
    "& disown",
    "chmod -r 777",
    "chmod 777 /",
    "| sh",
    "| bash",
    "> /dev/",
    "git push -u origin +",
    "shutdown",
    "reboot",
    "mkfifo ",
    "/dev/tcp/",
)


def _normalize_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", cmd.strip().lower())


def _rm_filesystem_root_dangerous(cmd: str) -> bool:
    """True if command looks like rm -rf / (root), not rm -rf /tmp/foo."""
    n = _normalize_cmd(cmd)
    return bool(
        re.search(r"\brm\s+(-[rf]+\s+)+/(?:\s|$|\*)", n)
        or re.search(r"\brm\s+(-[fr]+\s+)+/(?:\s|$|\*)", n)
    )


def _git_destructive_push(cmd: str) -> bool:
    n = _normalize_cmd(cmd)
    if "git push" not in n or "force-with-lease" in n:
        return False
    if "--force" in n:
        return True
    return bool(re.search(r"\s-f(\s|$)", n))


def _shell_denied_reason(cmd: str) -> str | None:
    n = _normalize_cmd(cmd)
    if _rm_filesystem_root_dangerous(cmd):
        return "blocked: rm targeting filesystem root /"
    for bad in _DENY_SUBSTRINGS:
        if bad in n:
            return f"blocked pattern: {bad!r}"
    if _git_destructive_push(cmd):
        return "blocked: git push --force / -f (not force-with-lease)"
    return None


def _shell_strict_allowed(cmd: str) -> bool:
    prefixes = os.getenv("SHELL_ALLOW_PREFIXES", "git ,pytest ,uv ,python ,echo ,ls ,cat ,head ,wc ,pwd").strip()
    if not prefixes:
        return False
    c = cmd.strip()
    for p in prefixes.split(","):
        p = p.strip()
        if p and c.startswith(p):
            return True
    return False


def check_shell_policy(cmd: str) -> str | None:
    """
    Returns error message if command must not run, else None.
    """
    policy = os.getenv("SHELL_POLICY", "deny").strip().lower()
    if policy in ("off", "none", "0", "false", "no"):
        return None
    if policy == "strict":
        if _shell_strict_allowed(cmd):
            return None
        return (
            "SHELL_POLICY=strict: command must start with one of "
            "SHELL_ALLOW_PREFIXES (comma-separated)."
        )
    if policy == "deny":
        return _shell_denied_reason(cmd)
    return f"Unknown SHELL_POLICY={policy!r}; use off|deny|strict"


def execute(params: dict) -> str:
    cmd = params.get("command", "")
    if not cmd:
        return "No command."

    blocked = check_shell_policy(cmd)
    if blocked:
        return f"❌ shell policy: {blocked}"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(ROOT),
        )
        out = result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout
        err = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
        return f"exit={result.returncode}\n{out}\n{err}".strip()
    except subprocess.TimeoutExpired:
        return "Command timed out (30s)."
    except Exception as e:
        return f"Error: {e}"
