"""扫描 00-Inbox/ 并分类原始文档；提取元数据并启发式预判材料体裁。"""

import logging
import re
from pathlib import Path

from compile_lib import count_chars


logger = logging.getLogger(__name__)


class UnsupportedDocumentError(ValueError):
    """不支持的文档格式。"""


# 当前支持的文本格式：Markdown、纯文本及其常见扩展名变体
TEXT_EXTS = {".md", ".txt", ".markdown"}
PDF_EXTS = {".pdf"}

# ---- 材料体裁（genre）识别 ----
# 五种主要体裁；LLM 确认时允许判出五类之外的体裁并标注具体名称
KNOWN_GENRES = {"book", "paper", "essay", "dialogue", "scrap"}
GENERIC_GENRE = "generic"  # 五类之外或未知体裁的兜底提取策略

# 启发式阈值（可调）
BOOK_MIN_TOC_CHAPTERS = 3      # PDF 目录章节数达到此值预判为图书
BOOK_MIN_PAGES = 100           # PDF 页数超过此值预判为图书
PAPER_MIN_ACADEMIC_MARKERS = 2 # 命中学术结构标记种类数达到此值预判为论文
DIALOGUE_MIN_LINE_RATIO = 0.3  # 对话标记行占比超过此值预判为对话录
SCRAP_MAX_CHARS = 3000         # 短于此等效字符数且无章节结构预判为零散材料

# 行首说话人模式：「张三：」「Q:」「我：」「【张三】」等；
# 排除以数字（时间戳 12:30）、Markdown 标记（#、-、*、>）开头的行
DIALOGUE_LINE_RE = re.compile(
    r"^(?:【(?P<bracket>[^】\n]{1,12})】|(?P<name>[^\s:：#>*\-\d【】][^\s:：\n]{0,11}))[:：]\s*\S"
)

# 对话录预判的附加条件：防止「灵感：xxx」这类单行标签式笔记被误判
DIALOGUE_MIN_LINES = 2     # 至少 2 行对话标记
DIALOGUE_MIN_SPEAKERS = 2  # 至少 2 个不同说话人

# 学术结构标记（不区分大小写），命中种类数用于论文预判
ACADEMIC_MARKER_RES = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"摘\s*要", r"\babstract\b", r"关键词|关键字", r"\bkeywords?\b",
        r"参考文献", r"\breferences\b", r"\barxiv\b", r"\bdoi\b",
    )
]

# Markdown ATX 标题
HEADING_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)


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


def _count_academic_markers(text: str) -> int:
    """统计文本命中的学术结构标记种类数。"""
    return sum(1 for r in ACADEMIC_MARKER_RES if r.search(text))


def _dialogue_speakers(text: str) -> list[str]:
    """提取全部对话标记行的说话人名（含【】形式）。"""
    speakers = []
    for ln in text.splitlines():
        m = DIALOGUE_LINE_RE.match(ln.strip())
        if m:
            speakers.append(m.group("bracket") or m.group("name"))
    return speakers


def _dialogue_line_ratio(text: str) -> float:
    """统计对话标记行在全部非空行中的占比。"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 0.0
    hits = sum(1 for ln in lines if DIALOGUE_LINE_RE.match(ln.strip()))
    return hits / len(lines)


def extract_metadata(path: Path, doc_type: str) -> dict:
    """
    提取材料的结构元数据，供体裁预判与 LLM 首读确认使用。

    返回字段：
    - char_count：等效字符数（PDF 为采样估算值）
    - dialogue_ratio：对话标记行占比
    - dialogue_lines / dialogue_speakers：对话标记行数 / 不同说话人数
    - academic_hits：命中的学术结构标记种类数
    - heading_count：Markdown ATX 标题数（PDF 恒为 0）
    - toc_chapters / page_count：仅 PDF 有值，其余为 0
    """
    meta = {
        "char_count": 0,
        "dialogue_ratio": 0.0,
        "dialogue_lines": 0,
        "dialogue_speakers": 0,
        "academic_hits": 0,
        "heading_count": 0,
        "toc_chapters": 0,
        "page_count": 0,
    }

    if doc_type == "text":
        text = path.read_text(encoding="utf-8")
        meta["char_count"] = count_chars(text)
        meta["dialogue_ratio"] = _dialogue_line_ratio(text)
        speakers = _dialogue_speakers(text)
        meta["dialogue_lines"] = len(speakers)
        meta["dialogue_speakers"] = len(set(speakers))
        meta["academic_hits"] = _count_academic_markers(text)
        meta["heading_count"] = len(HEADING_RE.findall(text))
    elif doc_type == "pdf":
        import fitz  # 延迟导入，纯文本场景不依赖 PyMuPDF

        from compile_lib.pdf_extractor import _estimate_chars_per_page

        with fitz.open(path) as doc:
            meta["page_count"] = len(doc)
            try:
                meta["toc_chapters"] = len(doc.get_toc())
            except Exception:
                meta["toc_chapters"] = 0
            sample_pages = min(5, len(doc))
            sample_text = "\n".join(
                doc[i].get_text() for i in range(sample_pages)
            )
            meta["char_count"] = int(
                _estimate_chars_per_page(doc) * len(doc)
            )
            meta["dialogue_ratio"] = _dialogue_line_ratio(sample_text)
            speakers = _dialogue_speakers(sample_text)
            meta["dialogue_lines"] = len(speakers)
            meta["dialogue_speakers"] = len(set(speakers))
            meta["academic_hits"] = _count_academic_markers(sample_text)
    else:
        raise ValueError(f"未知文档类型: {doc_type}")

    return meta


def predict_genre(meta: dict, doc_type: str) -> str:
    """
    基于元数据启发式预判材料体裁。

    返回 book / paper / dialogue / scrap / essay / unknown；
    unknown 与五类之外的情况交由 LLM 首读确认时判定。
    """
    if doc_type == "pdf":
        if (
            meta["toc_chapters"] >= BOOK_MIN_TOC_CHAPTERS
            or meta["page_count"] > BOOK_MIN_PAGES
        ):
            return "book"
        if meta["academic_hits"] >= PAPER_MIN_ACADEMIC_MARKERS:
            return "paper"
        return "unknown"

    # 文本文档
    if meta["academic_hits"] >= PAPER_MIN_ACADEMIC_MARKERS:
        return "paper"
    if (
        meta["dialogue_ratio"] > DIALOGUE_MIN_LINE_RATIO
        and meta["dialogue_lines"] >= DIALOGUE_MIN_LINES
        and meta["dialogue_speakers"] >= DIALOGUE_MIN_SPEAKERS
    ):
        return "dialogue"
    if meta["char_count"] < SCRAP_MAX_CHARS and meta["heading_count"] == 0:
        return "scrap"
    return "essay"


def extract_sample(path: Path, doc_type: str, max_chars: int = 1500) -> str:
    """
    提取材料的开头样本，供 LLM 首读确认体裁。
    文本取开头片段；PDF 取目录标题与前几页文本。
    """
    if doc_type == "text":
        return path.read_text(encoding="utf-8")[: max_chars * 2]

    if doc_type == "pdf":
        import fitz

        parts = []
        with fitz.open(path) as doc:
            try:
                toc_titles = [t for _, t, _ in doc.get_toc()]
            except Exception:
                toc_titles = []
            if toc_titles:
                parts.append("目录：" + " | ".join(toc_titles[:30]))
            sample_pages = min(3, len(doc))
            for i in range(sample_pages):
                parts.append(doc[i].get_text())
        return "\n".join(parts)[: max_chars * 2]

    raise ValueError(f"未知文档类型: {doc_type}")


def build_compile_plan(docs: list[dict]) -> list[dict]:
    """
    为扫描到的文档生成编译计划：元数据 + 启发式预判体裁 + 开头样本。
    每个元素：{"path", "doc_type", "metadata", "predicted_genre", "sample"}
    """
    plan = []
    for doc in docs:
        meta = extract_metadata(doc["path"], doc["doc_type"])
        plan.append({
            "path": doc["path"],
            "doc_type": doc["doc_type"],
            "metadata": meta,
            "predicted_genre": predict_genre(meta, doc["doc_type"]),
            "sample": extract_sample(doc["path"], doc["doc_type"]),
        })
    return plan
