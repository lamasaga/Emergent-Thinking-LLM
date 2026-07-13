import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compile_lib import count_chars, ensure_buffer_dirs
from compile_lib.ingest import scan_inbox, classify_file, UnsupportedDocumentError
from compile_lib.pdf_extractor import extract_pdf_toc_chunks, PdfExtractionError


def _make_pdf(path: Path, pages: list[str], toc: list | None = None):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # 使用支持中文的 CJK 字体，确保文本可正确提取
        page.insert_text((72, 72), text, fontname="china-ss")
    if toc:
        doc.set_toc(toc)
    doc.save(path)
    doc.close()


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


def test_extract_pdf_with_toc_single_chapter(tmp_path):
    pdf = tmp_path / "single_chapter.pdf"
    _make_pdf(pdf, ["第一章内容"], toc=[[1, "第一章", 1]])

    chunks = extract_pdf_toc_chunks(pdf, max_chars=30000)
    assert len(chunks) == 1
    assert chunks[0]["title"] == "第一章"
    assert chunks[0]["page_range"] == "1-1"
    assert "第一章内容" in chunks[0]["text"]
    assert chunks[0]["char_count"] > 0


def test_extract_pdf_without_toc_fallback(tmp_path):
    pdf = tmp_path / "no_toc.pdf"
    _make_pdf(pdf, ["第一页", "第二页", "第三页"])

    chunks = extract_pdf_toc_chunks(pdf, max_chars=30000)
    assert len(chunks) >= 1
    assert all("page_range" in c for c in chunks)
    assert all(c["text"] for c in chunks)


def test_extract_pdf_oversized_chapter(tmp_path):
    pdf = tmp_path / "oversized.pdf"
    # 第一章两页，每页重复大量字符使其超过 max_chars
    long_text = "第一章 " + "x " * 2000
    normal_text = "第二章内容"
    _make_pdf(
        pdf,
        [long_text, long_text, normal_text],
        toc=[[1, "第一章", 1], [1, "第二章", 3]],
    )

    chunks = extract_pdf_toc_chunks(pdf, max_chars=100)
    titles = [c["title"] for c in chunks]
    assert any("第二章" in t and "第一章" not in t for t in titles)
    assert all(c["char_count"] <= 100 for c in chunks)


def test_extract_pdf_empty(tmp_path):
    pdf = tmp_path / "empty.pdf"
    # PyMuPDF 无法保存 0 页 PDF，使用一页无文本的空白页测试空内容返回空列表
    _make_pdf(pdf, [""])

    chunks = extract_pdf_toc_chunks(pdf, max_chars=30000)
    assert chunks == []


def test_extract_pdf_invalid_path(tmp_path):
    missing = tmp_path / "missing.pdf"
    with pytest.raises(PdfExtractionError):
        extract_pdf_toc_chunks(missing, max_chars=30000)


def test_extract_pdf_all_chunks_within_limit(tmp_path):
    pdf = tmp_path / "within_limit.pdf"
    _make_pdf(
        pdf,
        ["alpha beta", "charlie delta", "echo foxtrot"],
        toc=[[1, "第一部分", 1], [1, "第二部分", 3]],
    )

    chunks = extract_pdf_toc_chunks(pdf, max_chars=50)
    assert isinstance(chunks, list)
    assert all(c["char_count"] <= 50 for c in chunks)
    assert all(c["text"] for c in chunks)
