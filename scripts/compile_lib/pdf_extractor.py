"""PDF 文本、目录与页码提取。"""

import re
from pathlib import Path


try:
    import fitz  # PyMuPDF
except ImportError as e:
    raise ImportError("PDF 处理需要 PyMuPDF，请运行：python -m pip install pymupdf") from e


class PdfExtractionError(RuntimeError):
    """PDF 提取失败。"""


def _estimate_chars_per_page(doc: fitz.Document) -> float:
    """采样前 5 页估算平均每页字数。"""
    samples = []
    for page in doc[:5]:
        text = page.get_text()
        # 粗略估算：中文字符 + 英文单词
        cn = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
        en = len(re.findall(r"[a-zA-Z]+", text))
        samples.append(cn + en)
    return sum(samples) / len(samples) if samples else 500


def _split_by_page_ranges(doc: fitz.Document, max_chars: int) -> list[dict]:
    """按页码范围切分，尽量让每段字数 ≤ max_chars。"""
    chars_per_page = _estimate_chars_per_page(doc)
    pages_per_chunk = max(1, int(max_chars / max(chars_per_page, 1)))

    chunks = []
    start = 0
    total = len(doc)
    while start < total:
        end = min(start + pages_per_chunk, total)
        text_parts = []
        for page in doc[start:end]:
            text_parts.append(page.get_text())
        text = "\n".join(text_parts)
        chunks.append({
            "title": f"页码 {start + 1}-{end}",
            "page_range": f"{start + 1}-{end}",
            "text": text,
        })
        start = end
    return chunks


def extract_pdf_toc_chunks(path: Path, max_chars: int = 30000) -> list[dict]:
    """
    提取 PDF 文本并按目录/页码切分为编译单元。
    返回列表元素：{"title", "page_range", "text", "char_count"}
    """
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise PdfExtractionError(f"无法打开 PDF {path}: {e}") from e

    toc = doc.get_toc()
    chunks = []

    if toc:
        # 目录驱动切分
        for i, entry in enumerate(toc):
            level, title, page = entry
            end_page = toc[i + 1][2] if i + 1 < len(toc) else len(doc) + 1
            start_idx = max(0, page - 1)
            end_idx = min(end_page - 1, len(doc))
            text_parts = []
            for page_obj in doc[start_idx:end_idx]:
                text_parts.append(page_obj.get_text())
            text = "\n".join(text_parts)
            if len(text) > max_chars:
                # 单章过大，继续按页码切分
                sub_chunks = _split_by_page_ranges(doc, max_chars)
                for sc in sub_chunks:
                    sc["title"] = f"{title} / {sc['title']}"
                chunks.extend(sub_chunks)
            else:
                chunks.append({
                    "title": title,
                    "page_range": f"{page}-{end_page - 1}",
                    "text": text,
                })
    else:
        chunks = _split_by_page_ranges(doc, max_chars)

    doc.close()

    # 统一补充 char_count
    from compile_lib import count_chars
    for c in chunks:
        c["char_count"] = count_chars(c["text"])

    return chunks
