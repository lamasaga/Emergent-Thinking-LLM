import sys
from pathlib import Path

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compile_lib import count_chars, ensure_buffer_dirs
from compile_lib.chunker import (
    _ceil_half,
    _split_long_sentence,
    _split_text_by_paragraphs,
    _tokenize_for_count,
    build_compile_units,
)
from compile_lib.ingest import scan_inbox, classify_file, UnsupportedDocumentError
from compile_lib.pdf_extractor import extract_pdf_toc_chunks, PdfExtractionError, _split_by_page_ranges
from compile_lib.batch_runner import build_batches, format_batch_prompt


def _make_pdf(path: Path, pages: list[str], toc: list | None = None, font_size: float = 12.0):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # 使用文本框与较小字号，确保大量文本能被渲染和提取
        rect = fitz.Rect(72, 72, page.rect.width - 72, page.rect.height - 72)
        page.insert_textbox(rect, text, fontsize=font_size, fontname="china-ss")
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


def test_tokenize_for_count_matches_count_chars():
    text = "Hello 世界，this is a test。"
    tokens = _tokenize_for_count(text)
    total_cost = sum(cost for _, cost in tokens)
    assert _ceil_half(total_cost) == count_chars(text)


def test_split_long_sentence_mixed_language():
    # 中英文混合，每个英文单词 2 等效字符，每个中文字符 1 等效字符
    sentence = "Hello World " * 10 + "世界" * 20
    max_chars = 20
    chunks = _split_long_sentence(sentence, max_chars)
    assert len(chunks) > 1
    assert all(count_chars(c) <= max_chars for c in chunks)


def test_split_long_sentence_long_english():
    sentence = "word " * 100
    max_chars = 20
    chunks = _split_long_sentence(sentence, max_chars)
    assert len(chunks) > 1
    assert all(count_chars(c) <= max_chars for c in chunks)


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
    # 第一章 3 页，每页约 400 等效中文字符，确保单页不超过 max_chars
    # 但章节总字符数超过 max_chars，从而触发按页码拆分
    dense_text = "密" * 400
    chapter1_pages = [dense_text] * 3
    chapter2_text = "第二章内容"
    _make_pdf(
        pdf,
        [*chapter1_pages, chapter2_text],
        toc=[[1, "第一章", 1], [1, "第二章", 4]],
    )

    chunks = extract_pdf_toc_chunks(pdf, max_chars=500)
    titles = [c["title"] for c in chunks]

    # 第二章仍是独立 chunk
    assert any("第二章" in t and "第一章" not in t for t in titles)
    # 第一章被拆分为多个子 chunk
    chapter1_chunks = [c for c in chunks if "第一章" in c["title"]]
    assert len(chapter1_chunks) > 1
    assert all("页码" in c["title"] for c in chapter1_chunks)
    # 所有 chunk 均不超过 max_chars
    assert all(c["char_count"] <= 500 for c in chunks)


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


def test_extract_pdf_max_chars_non_positive(tmp_path):
    pdf = tmp_path / "any.pdf"
    _make_pdf(pdf, ["内容"])

    with pytest.raises(ValueError):
        extract_pdf_toc_chunks(pdf, max_chars=0)
    with pytest.raises(ValueError):
        extract_pdf_toc_chunks(pdf, max_chars=-1)


def test_extract_pdf_toc_edge_pages(tmp_path):
    pdf = tmp_path / "edge_toc.pdf"
    _make_pdf(
        pdf,
        ["第一页内容", "第二页内容", "第三页内容"],
        toc=[
            [1, "零页码", 0],
            [1, "负页码", -1],
            [1, "第一章", 1],
            [1, "第二章", 2],
            [1, "超长篇", 5],
        ],
    )

    chunks = extract_pdf_toc_chunks(pdf, max_chars=30000)
    titles = [c["title"] for c in chunks]
    assert "第一章" in titles
    assert "第二章" in titles
    # 零页码、负页码、超长篇等异常条目被钳位后不应导致错误或空 chunk
    assert all(c["text"] for c in chunks)
    # 所有页码范围必须在文档有效页数之内
    assert all(1 <= int(c["page_range"].split("-")[0]) <= 3 for c in chunks)
    assert all(1 <= int(c["page_range"].split("-")[-1]) <= 3 for c in chunks)


def test_split_by_page_ranges_with_bounds(tmp_path):
    pdf = tmp_path / "bounds.pdf"
    # 第一页稀疏，后续页密集，用于触发估算偏小后的窗口收缩
    _make_pdf(pdf, ["稀" * 50, "密" * 300, "集" * 300, "中" * 300])

    with fitz.open(pdf) as doc:
        chunks = _split_by_page_ranges(doc, max_chars=500, start=1, end=3)
        page_ranges = [c["page_range"] for c in chunks]
        # start=1, end=3 表示只处理第 2-3 页（0-based 索引 [1, 3)）
        assert page_ranges == ["2-2", "3-3"]
        assert all(count_chars(c["text"]) <= 500 for c in chunks)
        # 文本框换行导致字符被拆散，使用 count 验证内容归属
        assert chunks[0]["text"].count("密") >= 300
        assert chunks[1]["text"].count("集") >= 300


def test_split_by_page_ranges_single_page_exceeds(tmp_path):
    pdf_path = tmp_path / "dense.pdf"
    # 创建一页就超过 100 字符的 PDF
    text = "密" * 200
    _make_pdf(pdf_path, [text], font_size=6.0)

    doc = fitz.open(pdf_path)
    chunks = _split_by_page_ranges(doc, max_chars=100)
    doc.close()

    assert len(chunks) == 1
    assert chunks[0]["char_count"] > 100
    assert "1-1" in chunks[0]["page_range"]


def test_split_by_page_ranges_empty_range(tmp_path):
    pdf_path = tmp_path / "empty_range.pdf"
    _make_pdf(pdf_path, ["page one"])

    doc = fitz.open(pdf_path)
    chunks = _split_by_page_ranges(doc, max_chars=500, start=1, end=1)
    doc.close()

    assert chunks == []


def test_build_compile_units_text(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    article = inbox / "article.md"
    article.write_text("# Title\n\n" + "正文。" * 100, encoding="utf-8")

    units = build_compile_units([{"path": article, "doc_type": "text"}], max_chars=30000)
    assert len(units) == 1
    assert units[0]["doc_type"] == "text"
    assert units[0]["source_path"] == article


def test_build_compile_units_text_split(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    article = inbox / "long.md"
    # 生成 >3 万字的文本
    article.write_text("# 标题\n\n" + "这是一个很长的段落。" * 4000, encoding="utf-8")

    units = build_compile_units([{"path": article, "doc_type": "text"}], max_chars=30000)
    assert len(units) > 1
    assert all(u["char_count"] <= 30000 for u in units)


def test_split_text_by_paragraphs_empty():
    assert _split_text_by_paragraphs("", max_chars=10) == []


def test_split_text_by_paragraphs_single_paragraph():
    text = "这是一个简短的段落。"
    chunks = _split_text_by_paragraphs(text, max_chars=100)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_split_text_by_paragraphs_multiple_paragraphs():
    para1 = "第一段。" * 5
    para2 = "第二段。" * 5
    para3 = "第三段。" * 5
    text = "\n\n".join([para1, para2, para3])
    chunks = _split_text_by_paragraphs(text, max_chars=30)
    assert len(chunks) == 2
    assert para1 in chunks[0]
    assert para2 in chunks[0]
    assert para3 in chunks[1]


def test_split_text_by_paragraphs_oversized_paragraph():
    para = "句子一。" * 20
    chunks = _split_text_by_paragraphs(para, max_chars=30)
    assert len(chunks) >= 2
    assert all(count_chars(c) <= 30 for c in chunks)


def test_split_text_by_paragraphs_oversized_sentence():
    sentence = "密" * 50
    text = sentence + "。"
    chunks = _split_text_by_paragraphs(text, max_chars=20)
    assert len(chunks) >= 2
    assert all(count_chars(c) <= 20 for c in chunks)


def test_split_text_by_paragraphs_flush_before_oversized():
    text = "短段落A。\n\n短段落B。\n\n" + "很长。" * 100
    chunks = _split_text_by_paragraphs(text, max_chars=20)
    assert len(chunks) >= 2
    assert chunks[0] == "短段落A。\n\n短段落B。"
    assert all(count_chars(c) <= 20 for c in chunks)


def test_build_compile_units_pdf(tmp_path):
    pdf = tmp_path / "book.pdf"
    _make_pdf(pdf, ["第一章内容"], toc=[[1, "第一章", 1]])

    units = build_compile_units([{"path": pdf, "doc_type": "pdf"}], max_chars=30000)
    assert len(units) >= 1
    assert units[0]["doc_type"] == "pdf"
    assert units[0]["source_path"] == pdf
    assert units[0]["title"] == "第一章"
    assert units[0]["page_range"] == "1-1"


def test_build_compile_units_unknown_type(tmp_path):
    doc = tmp_path / "weird.xyz"
    doc.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="未知文档类型"):
        build_compile_units([{"path": doc, "doc_type": "xyz"}])


def test_build_compile_units_max_chars_non_positive(tmp_path):
    md = tmp_path / "article.md"
    md.write_text("content", encoding="utf-8")
    with pytest.raises(ValueError, match="max_chars 必须为正数"):
        build_compile_units([{"path": md, "doc_type": "text"}], max_chars=0)


def test_compile_unit_schema(tmp_path):
    md = tmp_path / "schema_test.md"
    md.write_text("# Title\n\n正文内容。", encoding="utf-8")
    units = build_compile_units([{"path": md, "doc_type": "text"}], max_chars=30000)
    assert len(units) == 1
    unit = units[0]
    expected_fields = {
        "unit_id", "source_path", "doc_type", "title",
        "page_range", "section", "char_count", "text", "archivable",
    }
    assert set(unit.keys()) == expected_fields
    assert unit["unit_id"] == "schema_test-001"


def test_build_batches_simple():
    units = [
        {"unit_id": "u1", "char_count": 10000, "text": "a" * 10000},
        {"unit_id": "u2", "char_count": 15000, "text": "b" * 15000},
        {"unit_id": "u3", "char_count": 20000, "text": "c" * 20000},
    ]
    batches = build_batches(units, max_chars=30000)
    assert len(batches) == 2
    assert len(batches[0]) == 2
    assert len(batches[1]) == 1


def test_build_batches_oversized_unit():
    units = [
        {"unit_id": "u1", "char_count": 50000, "text": "x" * 50000},
    ]
    batches = build_batches(units, max_chars=30000)
    assert len(batches) == 1
    assert batches[0][0]["unit_id"] == "u1"


def test_format_batch_prompt():
    units = [
        {
            "unit_id": "u1",
            "source_path": Path("00-Inbox/a.md"),
            "doc_type": "text",
            "title": "a.md",
            "section": "",
            "page_range": "",
            "char_count": 10,
            "text": "内容",
        }
    ]
    prompt = format_batch_prompt(units)
    assert "a.md" in prompt
    assert "内容" in prompt
    assert "原子化拆解" in prompt
