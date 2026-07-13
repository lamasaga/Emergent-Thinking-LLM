"""将原始文档切分为编译单元。"""

from pathlib import Path

from compile_lib import count_chars
from compile_lib.pdf_extractor import extract_pdf_toc_chunks


def _split_text_by_paragraphs(text: str, max_chars: int) -> list[str]:
    """按自然段落切分文本，每段 ≤ max_chars。"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = count_chars(para)
        if para_len > max_chars:
            # 单段就超过上限，强制切分（按句子）
            sentences = [s.strip() for s in para.split("。") if s.strip()]
            for sentence in sentences:
                s_len = count_chars(sentence)
                if current_len + s_len > max_chars and current:
                    chunks.append("\n\n".join(current))
                    current = []
                    current_len = 0
                current.append(sentence + "。")
                current_len += s_len
            continue

        if current_len + para_len > max_chars and current:
            chunks.append("\n\n".join(current))
            current = []
            current_len = 0

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

    return units
