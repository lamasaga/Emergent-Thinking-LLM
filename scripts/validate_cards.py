#!/usr/bin/env python3
"""
卡片一致性校验脚本

运行方式：
    python scripts/validate_cards.py

检查项：
1. frontmatter 必填字段完整性（id, title, type, created, updated, status）
2. id 唯一性
3. type 有效性
4. 正文与 relations 中的链接是否指向真实存在的卡片（幽灵链接检测）
5. relations 数量是否超过建议上限 6
6. 实例引用数量是否超过上限 6
7. 是否存在未被领域卡片引用的 orphan 实例卡片
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
CARDS_DIR = ROOT / "01-Cards"
DOMAINS_DIR = CARDS_DIR / "domains"

REQUIRED_FIELDS = {"id", "title", "type", "created", "updated", "status"}
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
RELATION_LIMIT = 6
INSTANCE_LIMIT = 6
LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


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


def get_relation_targets(fm_text: str):
    """提取 relations 中所有 target 字段值。"""
    return re.findall(r'target:\s*["\']?([^"\',\n]+)', fm_text)


def count_sources(fm_text: str):
    """统计 sources 列表项数量。"""
    m = re.search(r"^sources:\s*\n((?:\s*-[^\n]*\n)*)", fm_text, re.MULTILINE)
    if not m:
        return 0
    return len(re.findall(r"^\s*-", m.group(1), re.MULTILINE))


def count_instances(body: str):
    """统计正文 `## 实例` 部分下的列表项数量。"""
    m = re.search(r"## 实例[^\n]*\n(.*?)(?=## |\Z)", body, re.DOTALL)
    if not m:
        return 0
    return len(re.findall(r"^-", m.group(1), re.MULTILINE))


def collect_card_files():
    """收集所有卡片文件路径。"""
    files = []
    if DOMAINS_DIR.exists():
        files.extend(DOMAINS_DIR.glob("*.md"))
    for subdir in CARDS_DIR.iterdir():
        if subdir.is_dir() and subdir.name not in ("_meta", "domains"):
            files.extend(subdir.glob("*.md"))
    return files


def main():
    errors = []
    warnings = []

    card_files = collect_card_files()
    id_to_file: dict[str, Path] = {}
    file_to_meta: dict[Path, dict] = {}

    # ---------- 第一阶段：解析并检查基础元数据 ----------
    for f in card_files:
        rel = f.relative_to(ROOT)
        content = f.read_text(encoding="utf-8")
        fm_text, body = extract_frontmatter(content)

        if fm_text is None:
            errors.append(f"{rel}: 缺少 frontmatter")
            continue

        meta = {"path": f, "fm_text": fm_text, "body": body}
        file_to_meta[f] = meta

        # 必填字段
        for field in REQUIRED_FIELDS:
            if get_field(fm_text, field) is None:
                errors.append(f"{rel}: 缺少必填字段 '{field}'")

        card_type = get_field(fm_text, "type")
        if card_type and card_type not in VALID_TYPES:
            errors.append(f"{rel}: 未知 type '{card_type}'")

        cid = get_field(fm_text, "id")
        if cid:
            if cid in id_to_file:
                errors.append(
                    f"{rel}: id '{cid}' 与 {id_to_file[cid].relative_to(ROOT)} 重复"
                )
            else:
                id_to_file[cid] = f
            meta["id"] = cid
        meta["type"] = card_type

    # ---------- 第二阶段：检查链接、relations、实例引用、orphan ----------
    referenced_instance_ids: set[str] = set()

    for f, meta in file_to_meta.items():
        rel = f.relative_to(ROOT)
        fm_text = meta["fm_text"]
        body = meta["body"]
        cid = meta.get("id", "")

        # 正文幽灵链接
        for link_id in LINK_PATTERN.findall(body):
            if link_id not in id_to_file:
                errors.append(f"{rel}: 幽灵链接 [[{link_id}]]")

        # relations 上限与目标存在性
        relation_targets = get_relation_targets(fm_text)
        if len(relation_targets) > RELATION_LIMIT:
            warnings.append(
                f"{rel}: relations 数量 {len(relation_targets)} 超过建议上限 {RELATION_LIMIT}"
            )
        for target in relation_targets:
            if target not in id_to_file:
                errors.append(f"{rel}: relations 指向不存在的卡片 '{target}'")

        # sources 上限
        source_count = count_sources(fm_text)
        if source_count > INSTANCE_LIMIT:
            warnings.append(
                f"{rel}: sources 数量 {source_count} 超过上限 {INSTANCE_LIMIT}"
            )

        # 实例引用上限
        instance_count = count_instances(body)
        if instance_count > INSTANCE_LIMIT:
            warnings.append(
                f"{rel}: 实例引用数量 {instance_count} 超过上限 {INSTANCE_LIMIT}"
            )

        # 收集领域卡片对实例的引用
        if meta.get("type") == "domain":
            for link_id in LINK_PATTERN.findall(body):
                referenced_instance_ids.add(link_id)
            for target in relation_targets:
                referenced_instance_ids.add(target)

    # ---------- 第三阶段：orphan 卡片检查 ----------
    for f, meta in file_to_meta.items():
        rel = f.relative_to(ROOT)
        if meta.get("type") == "domain":
            continue

        cid = meta.get("id")
        if not cid:
            continue

        if cid in referenced_instance_ids:
            continue

        # 检查是否被其他实例卡片引用
        referenced_by_instance = False
        for other_f, other_meta in file_to_meta.items():
            if other_f == f:
                continue
            other_body = other_meta["body"]
            if re.search(rf"\[\[{re.escape(cid)}(?:\||\]\])", other_body):
                referenced_by_instance = True
                break
            for target in get_relation_targets(other_meta["fm_text"]):
                if target == cid:
                    referenced_by_instance = True
                    break
            if referenced_by_instance:
                break

        if not referenced_by_instance:
            warnings.append(f"{rel}: orphan 卡片（未被任何领域卡片引用）")

    # ---------- 输出报告 ----------
    print("=" * 60)
    print(f"卡片校验报告 ({datetime.now().isoformat()})")
    print(f"扫描卡片数：{len(card_files)}")
    print(f"错误数：{len(errors)}")
    print(f"警告数：{len(warnings)}")
    print("=" * 60)

    if errors:
        print("\n## 错误")
        for e in errors:
            print(f"  ❌ {e}")

    if warnings:
        print("\n## 警告")
        for w in warnings:
            print(f"  ⚠️  {w}")

    if not errors and not warnings:
        print("\n✅ 所有卡片检查通过")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
