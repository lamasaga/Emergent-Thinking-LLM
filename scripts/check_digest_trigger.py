#!/usr/bin/env python3
"""
Buffer 消化触发检查脚本

运行方式：
    python scripts/check_digest_trigger.py [阈值]

功能：
- 统计 05-Buffer/ 中 status: scratch 的文件数量。
- 如果数量 >= 阈值（默认 10，可通过环境变量 BUFFER_DIGEST_THRESHOLD 或命令行参数覆盖），
  则返回非零退出码，表示应触发 /digest。

在 /compile 执行完毕后调用此脚本，可实现「scratch 堆积到一定量自动触发消化」的机制。
"""

import os
import re
import sys
from pathlib import Path

# 在 Windows Git Bash 等 GBK 终端下保证 Unicode 输出正常
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BUFFER_DIR = ROOT / "05-Buffer"
DEFAULT_THRESHOLD = 10
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
STATUS_PATTERN = re.compile(r"^status:\s*['\"]?(scratch)['\"]?$", re.MULTILINE)


def count_scratch_files():
    count = 0
    if not BUFFER_DIR.exists():
        return count
    for subdir in BUFFER_DIR.iterdir():
        if not subdir.is_dir():
            continue
        for f in subdir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            m = FRONTMATTER_PATTERN.match(content)
            if not m:
                continue
            if STATUS_PATTERN.search(m.group(1)):
                count += 1
    return count


def main():
    threshold = DEFAULT_THRESHOLD
    env_threshold = os.environ.get("BUFFER_DIGEST_THRESHOLD")
    if env_threshold and env_threshold.isdigit():
        threshold = int(env_threshold)
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        threshold = int(sys.argv[1])

    scratch_count = count_scratch_files()

    print(f"scratch Buffer 数量：{scratch_count}")
    print(f"消化触发阈值：{threshold}")

    if scratch_count >= threshold:
        print(f"达到阈值，建议自动触发 /digest。")
        return 1

    print("未达到阈值，无需触发 /digest。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
