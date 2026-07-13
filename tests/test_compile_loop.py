import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from compile_lib import count_chars, ensure_buffer_dirs


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
