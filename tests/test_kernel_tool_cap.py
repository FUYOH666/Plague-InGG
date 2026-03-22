"""Tests for tool result size cap injected into LLM context."""



from kernel.core import cap_tool_result_for_context


def test_cap_disabled_zero(monkeypatch):
    monkeypatch.setenv("TOOL_RESULT_MAX_CHARS", "0")
    s = "x" * 100
    assert cap_tool_result_for_context(s) == s


def test_cap_no_trim_when_under_limit(monkeypatch):
    monkeypatch.setenv("TOOL_RESULT_MAX_CHARS", "5000")
    s = "short"
    assert cap_tool_result_for_context(s) == s


def test_cap_trims_with_notice(monkeypatch):
    monkeypatch.setenv("TOOL_RESULT_MAX_CHARS", "50")
    s = "a" * 100
    out = cap_tool_result_for_context(s)
    assert len(out) > 50
    assert "trimmed" in out
    assert out.startswith("a" * 50)
