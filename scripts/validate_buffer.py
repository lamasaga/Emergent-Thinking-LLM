#!/usr/bin/env python3
"""
Buffer 一致性校验脚本

运行方式：
    python scripts/validate_buffer.py

检查项：
1. Buffer 文件 frontmatter 必填字段（title, type, created, updated, status）
2. status 取值有效性
3. type 取值有效性
4. type 与所在子目录名称一致
5. 文件名符合 YYYY-MM-DD-HHMMSS-关键词.md 格式
6. 正文不包含 [[ ]] 链接
7. frontmatter 不包含 id 或 relations
8. scratch 文件数量是否超过建议阈值（默认 10）
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# 在 Windows Git Bash 等 GBK 终端下保证 Unicode 输出正常
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BUFFER_DIR = ROOT / "05-Buffer"
README_FILE = BUFFER_DIR / "README.md"

REQUIRED_FIELDS = {"title", "type", "created", "updated", "status"}
VALID_TYPES = {
    "domain",
    "notion",
    "principle",
    "phenomenon",
    "entity",
    "group",
    "model",
    "method",
    "conflict",
    "note",
}
VALID_STATUSES = {"scratch", "digested", "constructed"}
FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{6}-.+\.md$")
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
SCRATCH_THRESHOLD = 50


def extract_frontmatter(content: str):
    """返回 (frontmatter_text, body)；如果没有 frontmatter 返回 (None, None)。"""
    m = FRONTMATTER_PATTERN.match(content)
    if not m:
        return None, None
    return m.group(1), content[m.end():]


def get_field(fm_text: str, field: str):
    """从 frontmatter 文本中提取顶层字段值，去除首尾引号。"""
    pattern = rf"^{field}:\s*(.+?)$"
    m = re.search(pattern, fm_text, re.MULTILINE)
    if not m:
        return None
    value = m.group(1).strip()
    return value.strip('"').strip("'")


def collect_buffer_files():
    """收集所有 Buffer 文件路径。"""
    files = []
    if not BUFFER_DIR.exists():
        return files
    for subdir in BUFFER_DIR.iterdir():
        if not subdir.is_dir():
            continue
        files.extend(subdir.glob("*.md"))
    return files


def main():
    errors = []
    warnings = []

    buffer_files = collect_buffer_files()
    scratch_count = 0

    print("=" * 60)
    print(f"Buffer 校验报告 ({datetime.now().isoformat()})")
    print(f"扫描 Buffer 数：{len(buffer_files)}")
    print("=" * 60)

    for f in buffer_files:
        if f == README_FILE:
            continue

        rel = f.relative_to(ROOT)
        content = f.read_text(encoding="utf-8")
        fm_text, body = extract_frontmatter(content)

        if fm_text is None:
            errors.append(f"{rel}: 缺少 frontmatter")
            continue

        # 必填字段
        for field in REQUIRED_FIELDS:
            if get_field(fm_text, field) is None:
                errors.append(f"{rel}: 缺少必填字段 '{field}'")

        # status 有效性
        status = get_field(fm_text, "status")
        if status and status not in VALID_STATUSES:
            errors.append(f"{rel}: 未知 status '{status}'")
        if status == "scratch":
            scratch_count += 1

        # type 有效性
        btype = get_field(fm_text, "type")
        if btype and btype not in VALID_TYPES:
            errors.append(f"{rel}: 未知 type '{btype}'")

        # type 与目录一致
        expected_dir = f.parent.name
        if btype and expected_dir != btype:
            errors.append(
                f"{rel}: type '{btype}' 与所在目录 '{expected_dir}' 不一致"
            )

        # 文件名格式
        if not FILENAME_PATTERN.match(f.name):
            errors.append(
                f"{rel}: 文件名不符合 YYYY-MM-DD-HHMMSS-关键词.md 格式"
            )

        # 正文不含 [[ ]] 链接
        for link_id in LINK_PATTERN.findall(body):
            errors.append(f"{rel}: Buffer 正文禁止出现链接 [[{link_id}]]")

        # frontmatter 不含 id / relations
        for forbidden in ("id", "relations"):
            if get_field(fm_text, forbidden) is not None:
                errors.append(f"{rel}: Buffer frontmatter 禁止包含 '{forbidden}'")

    if scratch_count > SCRATCH_THRESHOLD:
        warnings.append(
            f"scratch Buffer 数量 {scratch_count} 超过建议阈值 {SCRATCH_THRESHOLD}，建议运行 /digest"
        )

    print(f"\nscratch 文件数：{scratch_count}")

    if errors:
        print("\n## 错误")
        for e in errors:
            print(f"  ❌ {e}")

    if warnings:
        print("\n## 警告")
        for w in warnings:
            print(f"  ⚠️  {w}")

    if not errors and not warnings:
        print("\n✅ 所有 Buffer 检查通过")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
