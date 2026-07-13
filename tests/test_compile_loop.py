import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compile_lib import count_chars, ROOT, INBOX_DIR, BUFFER_DIR, ARCHIVE_DIR


def test_count_chars_chinese():
    assert count_chars("这是一个测试") == 6


def test_count_chars_english():
    # 英文按词数 * 1.5 估算
    assert count_chars("This is a test") == 6


def test_count_chars_mixed():
    assert count_chars("Hello 世界") == 4  # 1.5*1 + 2 = 4 (approx)
