"""write_file shrink guard and str_replace_file."""

from pathlib import Path


from tools import str_replace_file
from tools import write_file

ROOT = Path(__file__).resolve().parent.parent


def test_str_replace_once():
    f = ROOT / "tests" / ".str_replace_fixture"
    try:
        f.write_text("one TWO three\n", encoding="utf-8")
        out = str_replace_file.execute(
            {"path": "tests/.str_replace_fixture", "old_string": "TWO", "new_string": "2"}
        )
        assert "✅" in out
        assert f.read_text() == "one 2 three\n"
        out2 = str_replace_file.execute(
            {
                "path": "tests/.str_replace_fixture",
                "old_string": "TWO",
                "new_string": "x",
            }
        )
        assert "not found" in out2.lower()
    finally:
        f.unlink(missing_ok=True)


def test_str_replace_ambiguous():
    f = ROOT / "tests" / ".str_replace_fixture2"
    try:
        f.write_text("x x x", encoding="utf-8")
        out = str_replace_file.execute(
            {"path": "tests/.str_replace_fixture2", "old_string": "x", "new_string": "y"}
        )
        assert "3" in out and ("unique" in out.lower() or "times" in out)
    finally:
        f.unlink(missing_ok=True)


def test_write_shrink_guard_blocks(monkeypatch):
    f = ROOT / "tests" / ".shrink_guard_tmp"
    try:
        monkeypatch.setenv("WRITE_FILE_SHRINK_GUARD", "1")
        monkeypatch.setenv("WRITE_FILE_MIN_LEN", "50")
        monkeypatch.setenv("WRITE_FILE_MIN_RATIO", "0.5")
        f.write_text("a" * 200, encoding="utf-8")
        out = write_file.execute({"path": "tests/.shrink_guard_tmp", "content": "short"})
        assert "Shrink guard" in out
    finally:
        monkeypatch.delenv("WRITE_FILE_SHRINK_GUARD", raising=False)
        monkeypatch.delenv("WRITE_FILE_MIN_LEN", raising=False)
        monkeypatch.delenv("WRITE_FILE_MIN_RATIO", raising=False)
        f.unlink(missing_ok=True)
