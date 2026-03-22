"""Shell tool policy (deny / strict / off)."""


import pytest

from tools.shell import check_shell_policy, execute


@pytest.fixture(autouse=True)
def restore_env(monkeypatch):
    """Restore SHELL_* after each test."""
    yield
    monkeypatch.delenv("SHELL_POLICY", raising=False)
    monkeypatch.delenv("SHELL_ALLOW_PREFIXES", raising=False)


def test_deny_blocks_rm_rf_root(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "deny")
    assert check_shell_policy("rm -rf /tmp/x") is None  # not root fs
    assert check_shell_policy("rm -rf /") is not None
    assert check_shell_policy("sudo rm -rf /*") is not None


def test_deny_allows_git_status(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "deny")
    assert check_shell_policy("git status") is None


def test_deny_blocks_force_push(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "deny")
    assert check_shell_policy("git push --force origin main") is not None
    assert check_shell_policy("git push -f") is not None
    assert check_shell_policy("git push --force-with-lease") is None


def test_off_allows_dangerous_pattern(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "off")
    assert check_shell_policy("rm -rf /") is None


def test_strict_prefix(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "strict")
    monkeypatch.setenv("SHELL_ALLOW_PREFIXES", "echo ,git ")
    assert check_shell_policy("echo ok") is None
    assert check_shell_policy("git status") is None
    assert check_shell_policy("rm -f x") is not None


def test_execute_returns_policy_message(monkeypatch):
    monkeypatch.setenv("SHELL_POLICY", "deny")
    out = execute({"command": "rm -rf /"})
    assert "policy" in out.lower() or "blocked" in out.lower()
