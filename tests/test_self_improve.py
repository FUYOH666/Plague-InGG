"""Isolated git repo tests for self_improve (no network, no real GitHub)."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SELF_IMPROVE_PATH = PROJECT_ROOT / "tools" / "self_improve.py"


def _load_self_improve():
    spec = importlib.util.spec_from_file_location("self_improve", str(SELF_IMPROVE_PATH))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def si_module():
    return _load_self_improve()


@pytest.fixture
def git_repo(tmp_path, si_module, monkeypatch):
    """Minimal repo with main, one file, and a trivial pytest."""
    repo = tmp_path
    (repo / "dummy.txt").write_text("v0\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_minimal.py").write_text(
        "def test_ok():\n    assert True\n",
        encoding="utf-8",
    )
    r = _run_git(repo, "init", "-b", "main")
    assert r.returncode == 0, r.stderr
    _run_git(repo, "config", "user.email", "test@example.com")
    _run_git(repo, "config", "user.name", "Test User")
    r = _run_git(repo, "add", "-A")
    assert r.returncode == 0
    r = _run_git(repo, "commit", "-m", "init")
    assert r.returncode == 0, r.stderr

    monkeypatch.setattr(si_module, "ROOT", repo)
    monkeypatch.setattr(si_module, "EVOLUTION_DIR", repo / "evolution")
    return repo, si_module


def test_start_writes_marker_and_branch(git_repo):
    repo, si = git_repo
    out = si.execute({"hypothesis": "try something", "action": "start"})
    assert "Evolution branch" in out
    assert "evolve-" in out
    marker = repo / "evolution" / ".active_evolve_branch"
    assert marker.exists()
    branch = marker.read_text(encoding="utf-8").strip()
    assert branch.startswith("evolve-")
    r = _run_git(repo, "branch", "--show-current")
    assert r.stdout.strip() == branch


def test_test_requires_evolve_branch(git_repo):
    repo, si = git_repo
    _run_git(repo, "checkout", "main")
    out = si.execute({"hypothesis": "x", "action": "test"})
    assert "Must be on evolve branch" in out or "No active evolve branch" in out


def test_full_cycle_commit(git_repo):
    repo, si = git_repo
    assert "Evolution branch" in si.execute({"hypothesis": "add feature", "action": "start"})
    (repo / "dummy.txt").write_text("v1\n", encoding="utf-8")
    test_out = si.execute({"hypothesis": "add feature", "action": "test"})
    assert "Tests passed" in test_out or "passed" in test_out.lower()
    commit_out = si.execute({"hypothesis": "add feature", "action": "commit"})
    assert "merged" in commit_out.lower() or "committed" in commit_out.lower()
    assert (repo / "dummy.txt").read_text(encoding="utf-8") == "v1\n"
    r = _run_git(repo, "branch", "--show-current")
    assert r.stdout.strip() == "main"
    assert not (repo / "evolution" / ".active_evolve_branch").exists()


def test_revert_clears_marker(git_repo):
    repo, si = git_repo
    si.execute({"hypothesis": "bad idea", "action": "start"})
    branch = (repo / "evolution" / ".active_evolve_branch").read_text(encoding="utf-8").strip()
    (repo / "dummy.txt").write_text("dirty\n", encoding="utf-8")
    out = si.execute({"hypothesis": "bad idea", "action": "revert"})
    assert "Reverted" in out
    assert not (repo / "evolution" / ".active_evolve_branch").exists()
    r = _run_git(repo, "branch", "--show-current")
    assert r.stdout.strip() == "main"
    br = _run_git(repo, "branch", "--list", branch)
    assert branch not in br.stdout
