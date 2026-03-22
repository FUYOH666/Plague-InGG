"""Optional seed/dao.md in system prompt."""

from kernel.core import build_system_prompt


def test_dao_section_when_file_exists(monkeypatch, tmp_path):
    d = tmp_path / "dao.md"
    d.write_text("RULE_DAO_X: test marker for DAO injection.", encoding="utf-8")
    monkeypatch.setattr("kernel.core.DAO_FILE", d)
    prompt = build_system_prompt({}, query_for_rag=None)
    assert "RULE_DAO_X" in prompt
    assert "# DAO" in prompt
    assert "seed/dao.md" in prompt
