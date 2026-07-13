"""将原始文档切分为编译单元。"""

import re
from pathlib import Path

from compile_lib import WORD_RE, count_chars
from compile_lib.pdf_extractor import extract_pdf_toc_chunks


# 当前句子拆分基于中文常用句末标点；对英文缩写/小数点（如 "e.g. v1.0"）会误切，
# 这是已知限制，因为项目主要处理中文文本。
SENTENCE_END_RE = re.compile(r"([。.?!？！])")


def _flush_current(current: list[str], current_len: int, chunks: list[str]) -> tuple[list[str], int]:
    """将当前缓冲区 flush 到 chunks，并返回新的缓冲区和长度。"""
    if current:
        chunks.append("\n\n".join(current))
    return [], 0


def _split_long_sentence(sentence: str, max_chars: int) -> list[str]:
    """对超长句子按等效字符数强制截断，确保每个子块 ≤ max_chars。"""
    if count_chars(sentence) <= max_chars:
        return [sentence]

    chunks = []
    current = []
    current_len = 0

    for ch in sentence:
        current.append(ch)
        current_len = count_chars("".join(current))
        if current_len >= max_chars:
            chunks.append("".join(current))
            current = []
            current_len = 0

    if current:
        chunks.append("".join(current))

    return chunks


def _split_text_by_paragraphs(text: str, max_chars: int) -> list[str]:
    """按自然段落切分文本，确保每个 chunk 的等效字符数 ≤ max_chars。"""
    if max_chars <= 0:
        raise ValueError("max_chars 必须为正数")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = count_chars(para)
        if para_len > max_chars:
            # 拆分超长段落前先 flush 当前缓冲区
            current, current_len = _flush_current(current, current_len, chunks)

            # 单段就超过上限，按句子切分
            parts = SENTENCE_END_RE.split(para)
            sentences = []
            for i in range(0, len(parts) - 1, 2):
                sentence = parts[i] + parts[i + 1]
                if sentence.strip():
                    sentences.append(sentence)
            if len(parts) % 2 == 1 and parts[-1].strip():
                sentences.append(parts[-1].strip())

            for sentence in sentences:
                s_len = count_chars(sentence)
                if s_len > max_chars:
                    # 单句仍超限，强制截断
                    current, current_len = _flush_current(current, current_len, chunks)
                    for sub in _split_long_sentence(sentence, max_chars):
                        sub_len = count_chars(sub)
                        if current_len + sub_len > max_chars and current:
                            current, current_len = _flush_current(current, current_len, chunks)
                        current.append(sub)
                        current_len += sub_len
                    continue

                if current_len + s_len > max_chars and current:
                    current, current_len = _flush_current(current, current_len, chunks)

                current.append(sentence)
                current_len += s_len
            continue

        if current_len + para_len > max_chars and current:
            current, current_len = _flush_current(current, current_len, chunks)

        current.append(para)
        current_len += para_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def build_compile_units(docs: list[dict], max_chars: int = 30000) -> list[dict]:
    """
    将扫描得到的文档列表转换为编译单元队列。
    每个单元包含：unit_id, source_path, doc_type, title, page_range,
                  section, char_count, text, archivable
    """
    if max_chars <= 0:
        raise ValueError("max_chars 必须为正数")
    units = []

    for doc in docs:
        path: Path = doc["path"]
        doc_type = doc["doc_type"]

        if doc_type == "text":
            text = path.read_text(encoding="utf-8")
            chunks = _split_text_by_paragraphs(text, max_chars)
            for idx, chunk_text in enumerate(chunks):
                units.append({
                    "unit_id": f"{path.stem}-{idx + 1:03d}",
                    "source_path": path,
                    "doc_type": "text",
                    "title": path.name,
                    "page_range": "",
                    "section": f"片段 {idx + 1}/{len(chunks)}" if len(chunks) > 1 else "",
                    "char_count": count_chars(chunk_text),
                    "text": chunk_text,
                    "archivable": False,
                })

        elif doc_type == "pdf":
            pdf_chunks = extract_pdf_toc_chunks(path, max_chars=max_chars)
            for idx, chunk in enumerate(pdf_chunks):
                units.append({
                    "unit_id": f"{path.stem}-{idx + 1:03d}",
                    "source_path": path,
                    "doc_type": "pdf",
                    "title": chunk["title"],
                    "page_range": chunk["page_range"],
                    "section": "",
                    "char_count": chunk["char_count"],
                    "text": chunk["text"],
                    "archivable": False,
                })

        else:
            raise ValueError(f"未知文档类型: {doc_type}")

    return units
