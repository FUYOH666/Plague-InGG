"""Optional seed/constitution.md in system prompt."""

from kernel.core import build_system_prompt


def test_constitution_section_when_file_exists(monkeypatch, tmp_path):
    c = tmp_path / "constitution.md"
    c.write_text("RULE_X: test marker for constitution injection.", encoding="utf-8")
    monkeypatch.setattr("kernel.core.CONSTITUTION_FILE", c)
    prompt = build_system_prompt({}, query_for_rag=None)
    assert "RULE_X" in prompt
    assert "constitution" in prompt.lower()
