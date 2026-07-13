import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compile_lib import count_chars, ensure_buffer_dirs
from compile_lib.ingest import scan_inbox, classify_file, UnsupportedDocumentError


def test_count_chars_chinese():
    assert count_chars("这是一个测试") == 6


def test_count_chars_english():
    # 英文按词数 * 1.5 估算
    assert count_chars("This is a test") == 6


def test_count_chars_mixed():
    assert count_chars("Hello 世界") == 4  # 1.5*1 + 2 = 4 (approx)


def test_count_chars_empty():
    assert count_chars("") == 0


def test_count_chars_only_non_word_chars():
    assert count_chars("123...!!!") == 0


def test_count_chars_hyphenated_word():
    # "well-known" 作为一个英文词，等效 2 个字符
    assert count_chars("well-known") == 2


def test_count_chars_contraction():
    # "don't" 作为一个英文词，等效 2 个字符
    assert count_chars("don't") == 2


def test_ensure_buffer_dirs(tmp_path):
    ensure_buffer_dirs(tmp_path)
    for subtype in (
        "domain", "notion", "principle", "phenomenon", "entity",
        "group", "model", "method", "conflict", "note",
    ):
        assert (tmp_path / subtype).is_dir()


def test_classify_file_text(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("# Hello\n", encoding="utf-8")
    assert classify_file(md) == "text"

    txt = tmp_path / "note.txt"
    txt.write_text("note", encoding="utf-8")
    assert classify_file(txt) == "text"


def test_classify_file_pdf(tmp_path):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    assert classify_file(pdf) == "pdf"


def test_classify_file_unsupported(tmp_path):
    doc = tmp_path / "image.png"
    doc.write_bytes(b"\x89PNG")
    with pytest.raises(UnsupportedDocumentError):
        classify_file(doc)


def test_classify_file_extensionless_text(tmp_path):
    doc = tmp_path / "extensionless_text"
    doc.write_text("plain utf-8 text", encoding="utf-8")
    assert classify_file(doc) == "text"


def test_classify_file_extensionless_binary(tmp_path):
    doc = tmp_path / "extensionless_binary"
    doc.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedDocumentError):
        classify_file(doc)


def test_classify_file_case_insensitive(tmp_path):
    md = tmp_path / "article.MD"
    md.write_text("# Hello", encoding="utf-8")
    assert classify_file(md) == "text"

    txt = tmp_path / "note.TXT"
    txt.write_text("note", encoding="utf-8")
    assert classify_file(txt) == "text"

    pdf = tmp_path / "book.PDF"
    pdf.write_bytes(b"%PDF-1.4 fake")
    assert classify_file(pdf) == "pdf"


def test_scan_inbox(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "a.md").write_text("# Article A", encoding="utf-8")
    (inbox / "b.txt").write_text("Note B", encoding="utf-8")
    (inbox / "c.pdf").write_bytes(b"%PDF-1.4 fake")
    (inbox / "d.png").write_bytes(b"\x89PNG")
    (inbox / ".gitkeep").write_text("", encoding="utf-8")

    docs = scan_inbox(inbox)
    names = {d["path"].name for d in docs}
    assert names == {"a.md", "b.txt", "c.pdf"}
    assert "d.png" not in names

    # inbox 不存在时返回空列表
    assert scan_inbox(tmp_path / "nonexistent") == []
