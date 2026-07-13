"""PDF 文本、目录与页码提取。"""

from pathlib import Path

from compile_lib import count_chars


try:
    import fitz  # PyMuPDF
except ImportError as e:
    raise ImportError("PDF 处理需要 PyMuPDF，请运行：python -m pip install pymupdf") from e


class PdfExtractionError(RuntimeError):
    """PDF 提取失败。"""


def _estimate_chars_per_page(doc: fitz.Document) -> float:
    """采样前 5 页估算平均每页等效中文字符数。"""
    samples = []
    try:
        for page in doc[:5]:
            try:
                text = page.get_text()
            except Exception as e:
                raise PdfExtractionError(f"提取页面文本失败: {e}") from e
            samples.append(count_chars(text))
    except Exception as e:
        if isinstance(e, PdfExtractionError):
            raise
        raise PdfExtractionError(f"估算每页字符数失败: {e}") from e

    return sum(samples) / len(samples) if samples else 500.0


def _split_by_page_ranges(
    doc: fitz.Document,
    max_chars: int,
    start: int = 0,
    end: int | None = None,
) -> list[dict]:
    """按页码范围切分，尽量让每段等效中文字符数 ≤ max_chars。

    切分策略以估算的每页字符数为起点，按页码窗口组装文本后校验实际字符数。
    若窗口超限且窗口仍大于单页，则缩小窗口重新切分；若单页本身已超过
    max_chars，则接受该 chunk 作为下限保证。
    """
    if end is None:
        end = len(doc)
    end = min(end, len(doc))
    start = max(0, start)

    chars_per_page = _estimate_chars_per_page(doc)
    pages_per_chunk = max(1, int(max_chars / max(chars_per_page, 1)))

    chunks = []
    cursor = start
    while cursor < end:
        chunk_end = min(cursor + pages_per_chunk, end)
        text_parts = []
        for page in doc[cursor:chunk_end]:
            try:
                text_parts.append(page.get_text())
            except Exception as e:
                raise PdfExtractionError(f"提取页面文本失败: {e}") from e
        text = "\n".join(text_parts)
        chars = count_chars(text)
        if chars > max_chars and pages_per_chunk > 1:
            pages_per_chunk = max(1, pages_per_chunk // 2)
            continue
        chunks.append({
            "title": f"页码 {cursor + 1}-{chunk_end}",
            "page_range": f"{cursor + 1}-{chunk_end}",
            "text": text,
        })
        pages_in_chunk = chunk_end - cursor
        cursor = chunk_end
        # 根据实际密度动态调整下一窗口，避免过度保守
        if chars > 0:
            actual_chars_per_page = chars / pages_in_chunk
            pages_per_chunk = max(1, int(max_chars / max(actual_chars_per_page, 1)))
    return chunks


def extract_pdf_toc_chunks(path: Path, max_chars: int = 30000) -> list[dict]:
    """
    提取 PDF 文本并按目录/页码切分为编译单元。
    返回列表元素：{"title", "page_range", "text", "char_count"}
    """
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")

    if not path.is_file():
        raise PdfExtractionError(f"PDF 路径不存在或不是文件: {path}")

    try:
        with fitz.open(path) as doc:
            try:
                toc = doc.get_toc()
            except Exception as e:
                raise PdfExtractionError(f"无法读取 PDF 目录: {e}") from e

            chunks: list[dict] = []

            if toc:
                # 目录驱动切分
                for i, entry in enumerate(toc):
                    level, title, page = entry
                    page = max(1, page)
                    end_page = (
                        toc[i + 1][2] if i + 1 < len(toc) else len(doc) + 1
                    )
                    end_page = max(page, end_page)

                    start_idx = max(0, page - 1)
                    end_idx = max(start_idx, min(end_page - 1, len(doc)))

                    text_parts = []
                    for page_obj in doc[start_idx:end_idx]:
                        try:
                            text_parts.append(page_obj.get_text())
                        except Exception as e:
                            raise PdfExtractionError(
                                f"提取页面文本失败: {e}"
                            ) from e
                    text = "\n".join(text_parts)

                    if count_chars(text) > max_chars:
                        # 单章过大，只在该章页范围内继续按页码切分
                        sub_chunks = _split_by_page_ranges(
                            doc, max_chars, start_idx, end_idx
                        )
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
    except Exception as e:
        if isinstance(e, PdfExtractionError):
            raise
        raise PdfExtractionError(f"提取 PDF 失败: {e}") from e

    # 统一补充 char_count 并过滤空文本块
    result = []
    for c in chunks:
        try:
            c["char_count"] = count_chars(c["text"])
        except Exception as e:
            raise PdfExtractionError(f"计算字符数失败: {e}") from e
        if c["text"]:
            result.append(c)

    return result
