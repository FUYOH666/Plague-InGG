"""Tests for tools — read_file, write_file, list_dir, repo_patch, shell, git_commit, run_tests."""

import os
import pytest
from pathlib import Path

import tools as tools_module


@pytest.fixture(autouse=True)
def tmp_project(tmp_path, monkeypatch):
    """Use a temporary directory as project root for all tests."""
    monkeypatch.setattr(tools_module, "PROJECT_ROOT", tmp_path)
    return tmp_path


class TestReadFile:
    def test_read_existing_file(self, tmp_project):
        (tmp_project / "hello.txt").write_text("hello world")
        result = tools_module.read_file("hello.txt")
        assert result == "hello world"

    def test_read_nonexistent_file(self):
        result = tools_module.execute_tool("read_file", {"path": "nonexistent.txt"})
        assert "[ERROR]" in result

    def test_read_nested_file(self, tmp_project):
        (tmp_project / "a" / "b").mkdir(parents=True)
        (tmp_project / "a" / "b" / "c.txt").write_text("deep")
        assert tools_module.read_file("a/b/c.txt") == "deep"


class TestWriteFile:
    def test_write_new_file(self, tmp_project):
        result = tools_module.write_file("output.txt", "content here")
        assert "OK" in result
        assert (tmp_project / "output.txt").read_text() == "content here"

    def test_write_creates_dirs(self, tmp_project):
        tools_module.write_file("new/dir/file.py", "print('hi')")
        assert (tmp_project / "new" / "dir" / "file.py").exists()

    def test_write_overwrites(self, tmp_project):
        tools_module.write_file("f.txt", "first")
        tools_module.write_file("f.txt", "second")
        assert (tmp_project / "f.txt").read_text() == "second"


class TestListDir:
    def test_list_root(self, tmp_project):
        (tmp_project / "a.txt").write_text("")
        (tmp_project / "b").mkdir()
        result = tools_module.list_dir("")
        assert "a.txt" in result
        assert "b/" in result

    def test_list_subdir(self, tmp_project):
        (tmp_project / "x" / "y").mkdir(parents=True)
        (tmp_project / "x" / "y" / "z.txt").write_text("")
        result = tools_module.list_dir("x/y")
        assert "z.txt" in result


class TestRepoPatch:
    def test_patch(self, tmp_project):
        (tmp_project / "f.py").write_text("x = 1\n")
        result = tools_module.repo_patch("f.py", "x = 1", "x = 2")
        assert "OK" in result
        assert (tmp_project / "f.py").read_text() == "x = 2\n"

    def test_patch_old_not_found(self, tmp_project):
        (tmp_project / "f.py").write_text("x = 1\n")
        result = tools_module.repo_patch("f.py", "y = 1", "y = 2")
        assert "[ERROR]" in result


class TestShell:
    def test_echo(self):
        result = tools_module.shell("echo hello")
        assert "hello" in result

    def test_exit_code(self):
        result = tools_module.shell("exit 42")
        assert "exit code: 42" in result or "42" in result


class TestGitCommit:
    def test_commit(self, tmp_project):
        os.system(f"cd {tmp_project} && git init -q && git config user.email 't@t' && git config user.name 'T'")
        (tmp_project / "file.txt").write_text("data")
        result = tools_module.git_commit("test: initial", ["file.txt"])
        assert "OK" in result or "committed" in result.lower()

    def test_commit_all(self, tmp_project):
        os.system(f"cd {tmp_project} && git init -q && git config user.email 't@t' && git config user.name 'T'")
        (tmp_project / "a.txt").write_text("a")
        (tmp_project / "b.txt").write_text("b")
        result = tools_module.git_commit("test: all")
        assert "OK" in result or "committed" in result.lower()


class TestRunTests:
    def test_run_self(self, tmp_project):
        (tmp_project / "tests").mkdir()
        (tmp_project / "tests" / "__init__.py").write_text("")
        (tmp_project / "tests" / "test_simple.py").write_text("def test_pass():\n    assert True\n")
        result = tools_module.run_tests("tests/")
        assert "PASSED" in result


class TestExecuteTool:
    def test_unknown_tool(self):
        result = tools_module.execute_tool("nonexistent", {})
        assert "[ERROR]" in result
        assert "Unknown tool" in result

    def test_bad_arguments(self):
        result = tools_module.execute_tool("read_file", {"wrong_param": "x"})
        assert "[ERROR]" in result


class TestPathSafety:
    def test_path_traversal_blocked(self):
        result = tools_module.execute_tool("read_file", {"path": "../../../etc/passwd"})
        assert "[ERROR]" in result

    def test_protected_paths_blocked(self, tmp_project):
        """Agent cannot modify evaluator/harness."""
        (tmp_project / "scripts").mkdir(exist_ok=True)
        (tmp_project / "scripts" / "evaluator.py").write_text("# evaluator")
        result = tools_module.write_file("scripts/evaluator.py", "hacked")
        assert "Protected" in result or "[ERROR]" in result
        assert (tmp_project / "scripts" / "evaluator.py").read_text() == "# evaluator"


class TestEvolutionLog:
    def test_read_empty(self, tmp_project):
        result = tools_module.evolution_log("read")
        assert "(empty" in result or "empty" in result.lower()

    def test_append_and_read(self, tmp_project):
        tools_module.evolution_log("append", "tried X, failed")
        result = tools_module.evolution_log("read")
        assert "tried X, failed" in result

    def test_append_requires_content(self):
        result = tools_module.evolution_log("append", "")
        assert "[ERROR]" in result

    def test_unknown_action(self):
        result = tools_module.evolution_log("invalid")
        assert "[ERROR]" in result


class TestGitDiff:
    def test_git_diff_no_repo(self, tmp_project):
        result = tools_module.git_diff()
        assert "no changes" in result or "ERROR" in result or "fatal" in result.lower()

    def test_git_diff_with_changes(self, tmp_project):
        os.system(f"cd {tmp_project} && git init -q && git config user.email 't@t' && git config user.name 'T'")
        (tmp_project / "f.txt").write_text("hello")
        result = tools_module.git_diff()
        assert "hello" in result or "f.txt" in result or "no changes" in result


class TestRunPython:
    def test_run_python_echo(self):
        result = tools_module.run_python("print(2 + 2)")
        assert "4" in result

    def test_run_python_error(self):
        result = tools_module.run_python("1/0")
        assert "exit code" in result or "Error" in result or "ZeroDivision" in result

    def test_run_python_via_execute(self):
        result = tools_module.execute_tool("run_python", {"code": "print('ok')"})
        assert "ok" in result


class TestTranscribeEmbeddingRerank:
    """Tests that don't require network — error handling only."""

    def test_transcribe_nonexistent(self, tmp_project):
        result = tools_module.transcribe_audio("nonexistent.ogg")
        assert "[ERROR]" in result
        assert "not found" in result or "File" in result

    def test_embedding_empty(self):
        result = tools_module.embedding("")
        assert "[ERROR]" in result

    def test_rerank_empty_docs(self):
        result = tools_module.rerank("query", [])
        assert "[ERROR]" in result
