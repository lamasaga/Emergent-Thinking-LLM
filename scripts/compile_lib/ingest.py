"""扫描 00-Inbox/ 并分类原始文档。"""

import logging
from pathlib import Path


logger = logging.getLogger(__name__)


class UnsupportedDocumentError(ValueError):
    """不支持的文档格式。"""


# 当前支持的文本格式：Markdown、纯文本及其常见扩展名变体
TEXT_EXTS = {".md", ".txt", ".markdown"}
PDF_EXTS = {".pdf"}


def classify_file(path: Path) -> str:
    """
    根据扩展名将文件分类为 text / pdf，不支持则抛异常。

    - 文本/PDF 均按扩展名判断，扩展名匹配不区分大小写。
    - 无扩展名文件会按 UTF-8 strict 解码采样内容，判断是否为文本。
    """
    if not path.is_file():
        raise UnsupportedDocumentError(f"不是文件: {path}")
    ext = path.suffix.lower()
    if ext in TEXT_EXTS or (ext == "" and _looks_like_text(path)):
        return "text"
    if ext in PDF_EXTS:
        return "pdf"
    raise UnsupportedDocumentError(f"不支持的文件格式: {path}")


def _looks_like_text(path: Path) -> bool:
    """
    无扩展名文件：采样前 1024 字节判断是否为可解码文本。

    使用 UTF-8 strict 解码；无法解码或读取失败时视为非文本。
    """
    try:
        with path.open("rb") as f:
            sample = f.read(1024)
        sample.decode("utf-8", errors="strict")
        return True
    except (UnicodeDecodeError, OSError):
        return False


def scan_inbox(inbox_dir: Path) -> list[dict]:
    """
    扫描 inbox 目录，返回文档元信息列表。
    每个元素：{"path": Path, "doc_type": str}
    排除 .gitkeep、隐藏文件、目录。
    """
    docs = []
    if not inbox_dir.exists():
        return docs
    for path in inbox_dir.iterdir():
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        try:
            doc_type = classify_file(path)
        except UnsupportedDocumentError as e:
            logger.warning("跳过：%s", e)
            continue
        docs.append({"path": path, "doc_type": doc_type})
    return docs
