#!/usr/bin/env python3
"""
/compile 循环分批编译入口脚本。

运行方式：
    python scripts/compile_loop.py [--max-chars 30000] [--dry-run]

功能：
- 扫描 00-Inbox/ 中的原始文档。
- 对 PDF 图书按目录/页码切分，对零散文档按段落切分。
- 每批 ≤ max_chars，循环生成结构化 prompt 供 LLM/agent 消费。
- 输出进度报告，最终归档原始文档。
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compile_lib
from compile_lib.batch_runner import build_batches, format_batch_prompt, validate_buffers
from compile_lib.chunker import build_compile_units
from compile_lib.ingest import scan_inbox


INBOX_DIR = compile_lib.INBOX_DIR
ARCHIVE_DIR = compile_lib.ARCHIVE_DIR
ensure_buffer_dirs = compile_lib.ensure_buffer_dirs


def archive_document(path: Path) -> Path:
    """将原始文档移动到 03-Archive/，保持文件名，冲突时加序号。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    target = ARCHIVE_DIR / path.name
    counter = 1
    while target.exists():
        stem = path.stem
        suffix = path.suffix
        target = ARCHIVE_DIR / f"{stem}-{counter}{suffix}"
        counter += 1
    shutil.move(str(path), str(target))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="/compile 循环分批编译")
    parser.add_argument(
        "--max-chars",
        type=int,
        default=30000,
        help="每批最大等效中文字符数（默认 30000）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只输出每批的提示词和计划，不调用 LLM、不写入 Buffer、不归档",
    )
    args = parser.parse_args(argv if argv is not None else [])

    if args.max_chars <= 0:
        print("错误：--max-chars 必须为正整数", file=sys.stderr)
        return 1

    ensure_buffer_dirs()

    docs = scan_inbox(INBOX_DIR)
    if not docs:
        print("00-Inbox/ 为空，无需编译。")
        return 0

    print(f"扫描到 {len(docs)} 个原始文档，开始生成编译单元...")
    units = build_compile_units(docs, max_chars=args.max_chars)
    print(f"生成 {len(units)} 个编译单元。")

    batches = build_batches(units, max_chars=args.max_chars)
    print(f"组织为 {len(batches)} 个批次，每批 ≤{args.max_chars} 字符。\n")

    processed_sources = set()

    for idx, batch in enumerate(batches, 1):
        batch_chars = sum(u["char_count"] for u in batch)
        sources = {u["source_path"].name for u in batch}
        print(f"--- 批次 {idx}/{len(batches)} ---")
        print(f"来源：{', '.join(sources)}")
        print(f"编译单元数：{len(batch)}，总字数：{batch_chars}")

        prompt = format_batch_prompt(batch)

        if args.dry_run:
            print("[dry-run] 提示词已生成，未调用 LLM。")
            print(prompt[:500] + "...\n")
            for unit in batch:
                processed_sources.add(unit["source_path"])
            continue

        # 在 Kimi Code CLI 环境中，实际 LLM 语义工作由 agent 执行。
        # 本脚本输出 prompt 与批次信息，由 agent 读取后继续处理。
        print("请将以下 prompt 交给 LLM 进行编译：")
        print(prompt)
        print("\n[等待 LLM 输出...]")

        for unit in batch:
            processed_sources.add(unit["source_path"])

    if not args.dry_run:
        print("\n校验新生成的 Buffer...")
        if not validate_buffers():
            print("❌ Buffer 校验失败，停止归档。")
            return 1

        print("归档原始文档...")
        for src_path in processed_sources:
            archive_document(src_path)

    print("\n=== /compile 循环分批编译报告 ===")
    print(f"原始文档数：{len(docs)}")
    print(f"编译单元数：{len(units)}")
    print(f"批次数：{len(batches)}")
    if not args.dry_run:
        print(f"已处理来源：{', '.join(p.name for p in processed_sources)}")
    print("==================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
