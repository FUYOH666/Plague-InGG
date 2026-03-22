"""Smoke tests for all tools with TOOL_SPEC and execute."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"

# Minimal params for tools that require them
MINIMAL_PARAMS = {
    "remember": {"text": "smoke test"},
    "read_file": {"path": "README.md"},
    "write_file": {"path": "tests/.smoke_test_tmp", "content": "x"},
    "str_replace_file": {
        "path": "tests/.smoke_str_replace",
        "old_string": "SMOKE_UNIQUE_MARKER",
        "new_string": "smoke_ok",
    },
    "shell": {"command": "echo ok"},
    "brave_search": {"query": "test", "count": 1},
    "create_tool": None,  # skip
    "self_improve": None,  # skip - modifies git
}


def discover_tools():
    """Discover tools with TOOL_SPEC and execute."""
    tools = {}
    for path in sorted(TOOLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(path.stem, str(path))
            module = importlib.util.module_from_spec(spec)
            sys.modules[path.stem] = module
            spec.loader.exec_module(module)
            if hasattr(module, "TOOL_SPEC") and hasattr(module, "execute"):
                tools[module.TOOL_SPEC["name"]] = module
        except Exception:
            pass
    return tools


@pytest.fixture(scope="module")
def tools():
    return discover_tools()


def test_tools_discovered(tools):
    """At least core tools should be discoverable."""
    assert len(tools) >= 6
    assert "remember" in tools
    assert "memory_manager" in tools
    assert "str_replace_file" in tools


@pytest.mark.parametrize(
    "tool_name",
    [
        "remember",
        "list_dir",
        "memory_manager",
        "read_file",
        "shell",
        "str_replace_file",
        "write_file",
    ],
)
def test_tool_execute_smoke(tools, tool_name):
    """Each tool executes without crashing and returns str."""
    if tool_name not in tools:
        pytest.skip(f"Tool {tool_name} not discovered")
    if tool_name in MINIMAL_PARAMS and MINIMAL_PARAMS[tool_name] is None:
        pytest.skip(f"Tool {tool_name} skipped (modifies state)")
    if tool_name == "str_replace_file":
        (ROOT / "tests" / ".smoke_str_replace").write_text(
            "SMOKE_UNIQUE_MARKER\n", encoding="utf-8"
        )
    module = tools[tool_name]
    p = MINIMAL_PARAMS.get(tool_name, {})
    try:
        result = module.execute(p)
    finally:
        if tool_name == "str_replace_file":
            (ROOT / "tests" / ".smoke_str_replace").unlink(missing_ok=True)
    assert isinstance(result, str), f"Tool {tool_name} must return str, got {type(result)}"
    if tool_name == "write_file":
        (ROOT / "tests" / ".smoke_test_tmp").unlink(missing_ok=True)


def test_memory_manager_status(tools):
    """memory_manager status returns str."""
    if "memory_manager" not in tools:
        pytest.skip("memory_manager not found")
    result = tools["memory_manager"].execute({"action": "status"})
    assert isinstance(result, str)
    assert "stream" in result.lower() or "archive" in result.lower()


def test_list_dir_empty_params(tools):
    """list_dir works with empty params (defaults to .)."""
    if "list_dir" not in tools:
        pytest.skip("list_dir not found")
    result = tools["list_dir"].execute({})
    assert isinstance(result, str)
