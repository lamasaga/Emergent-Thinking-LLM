"""compile_loop 公共常量与工具函数。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INBOX_DIR = ROOT / "00-Inbox"
BUFFER_DIR = ROOT / "05-Buffer"
ARCHIVE_DIR = ROOT / "03-Archive"

DEFAULT_BATCH_LIMIT = 30000

WORD_RE = re.compile(r"[a-zA-Z]+(?:['-][a-zA-Z]+)?")


def count_chars(text: str) -> int:
    """
    估算等效中文字符数。
    - 中文字符：+1
    - 英文单词：+1.5（向上取整）
    - 数字、标点、空白：忽略
    """
    chinese = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    english_words = len(WORD_RE.findall(text))
    # 等价于 math.ceil(english_words * 1.5)，用整数运算避免浮点
    return chinese + (english_words * 3 + 1) // 2


def ensure_buffer_dirs(base_dir: Path = BUFFER_DIR) -> None:
    """确保 05-Buffer/ 下存在 ontology 声明的 10 个 type 子目录。"""
    for subtype in (
        "domain", "notion", "principle", "phenomenon", "entity",
        "group", "model", "method", "conflict", "note",
    ):
        (base_dir / subtype).mkdir(parents=True, exist_ok=True)
