#!/usr/bin/env python3
"""
/compile 循环分批编译入口脚本（体裁感知版）。

运行方式：
    python scripts/compile_loop.py [--max-chars 30000] [--dry-run]
    python scripts/compile_loop.py --plan
    python scripts/compile_loop.py --genres "文件.md=essay,书.pdf=book" [--deep]

功能：
- 扫描 00-Inbox/ 中的原始文档，提取元数据并启发式预判材料体裁。
- --plan：只输出编译计划（元数据、预判体裁、开头样本），不写 Buffer、不归档。
- --genres：传入 LLM 首读确认后的体裁（按文件名精确匹配，未列出的沿用预判）。
- 按体裁切分编译单元（对话录按轮次，图书按目录章节，其余按段落/页码）。
- 每批 ≤ max_chars 且为同一体裁，生成体裁专属 prompt 供 LLM/agent 消费。
- --deep：深度编译模式，一篇文档独占批次，输出深度 prompt 与维度覆盖要求。
- 输出进度报告，最终校验 Buffer 并归档原始文档。
"""

import argparse
import shutil
import sys
from pathlib import Path

# 在 Windows Git Bash 等 GBK 终端下保证 Unicode 输出正常
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import compile_lib
from compile_lib.batch_runner import build_batches, format_batch_prompt, validate_buffers
from compile_lib.chunker import build_compile_units
from compile_lib.ingest import KNOWN_GENRES, build_compile_plan, scan_inbox


INBOX_DIR = compile_lib.INBOX_DIR
ARCHIVE_DIR = compile_lib.ARCHIVE_DIR
ensure_buffer_dirs = compile_lib.ensure_buffer_dirs

DEEP_MODE_DOC_GUARD = 5  # 深度编译模式下文档数超过此值时输出守卫提示


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


def parse_genres_arg(arg: str) -> dict:
    """
    解析 --genres 参数："文件名=体裁,文件名=体裁"。
    返回 {文件名: 体裁}；格式错误时抛 ValueError。
    """
    genres = {}
    if not arg:
        return genres
    for pair in arg.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"--genres 格式错误（缺少 '='）：{pair!r}")
        name, genre = pair.split("=", 1)
        name, genre = name.strip(), genre.strip()
        if not name or not genre:
            raise ValueError(f"--genres 格式错误：{pair!r}")
        genres[name] = genre
    return genres


def print_compile_plan(plan: list[dict]) -> None:
    """输出编译计划：每份材料的元数据、预判体裁与开头样本。"""
    print("=== /compile 编译计划（--plan） ===")
    print("请 LLM 阅读各材料的开头样本，确认或修正预判体裁，并判断作者视角（self/external）。")
    print("确认后运行：python scripts/compile_loop.py --genres \"文件名=体裁,...\"\n")
    for item in plan:
        meta = item["metadata"]
        print("---")
        print(f"文件：{item['path'].name}")
        print(f"格式：{item['doc_type']}")
        print(
            "元数据："
            f"字数≈{meta['char_count']}，"
            f"对话行占比={meta['dialogue_ratio']:.2f}，"
            f"对话行数={meta['dialogue_lines']}，"
            f"说话人数={meta['dialogue_speakers']}，"
            f"学术标记={meta['academic_hits']}，"
            f"标题数={meta['heading_count']}，"
            f"目录章节={meta['toc_chapters']}，"
            f"页数={meta['page_count']}"
        )
        print(f"预判体裁：{item['predicted_genre']}")
        print("开头样本：")
        print(item["sample"])
        print()
    print("=== 计划结束 ===")


def group_batches(
    units: list[dict],
    max_chars: int,
    deep: bool,
) -> list[list[dict]]:
    """
    组织批次。
    - 普通模式：同一体裁的单元合并分批（每批 ≤ max_chars）。
    - 深度模式：一篇文档独占批次，不与其他文档合并。
    """
    if deep:
        by_doc: dict = {}
        for unit in units:
            by_doc.setdefault(unit["source_path"], []).append(unit)
        batches = []
        for doc_units in by_doc.values():
            batches.extend(build_batches(doc_units, max_chars=max_chars))
        return batches

    by_genre: dict = {}
    for unit in units:
        by_genre.setdefault(unit.get("genre"), []).append(unit)
    batches = []
    for genre_units in by_genre.values():
        batches.extend(build_batches(genre_units, max_chars=max_chars))
    return batches


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="/compile 循环分批编译（体裁感知版）")
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
    parser.add_argument(
        "--plan",
        action="store_true",
        help="只输出编译计划（元数据、预判体裁、开头样本），不写 Buffer、不归档",
    )
    parser.add_argument(
        "--genres",
        type=str,
        default="",
        help='LLM 确认后的体裁，格式："文件名=体裁,..."，未列出的文件沿用预判',
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="深度编译模式：一篇文档独占批次，尽可能挖掘 Buffer 可能性",
    )
    args = parser.parse_args(argv if argv is not None else [])

    if args.max_chars <= 0:
        print("错误：--max-chars 必须为正整数", file=sys.stderr)
        return 1

    try:
        genre_overrides = parse_genres_arg(args.genres)
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1

    docs = scan_inbox(INBOX_DIR)
    if not docs:
        print("00-Inbox/ 为空，无需编译。")
        return 0

    print(f"扫描到 {len(docs)} 个原始文档，提取元数据并预判体裁...")
    plan = build_compile_plan(docs)

    if args.plan:
        print_compile_plan(plan)
        return 0

    # 合并体裁：LLM 确认值优先，未确认的沿用启发式预判
    inbox_names = {item["path"].name for item in plan}
    unknown_names = set(genre_overrides) - inbox_names
    if unknown_names:
        print(
            f"警告：--genres 中的文件名不在 Inbox 中：{', '.join(sorted(unknown_names))}",
            file=sys.stderr,
        )
    final_genres = {}
    for item in plan:
        name = item["path"].name
        genre = genre_overrides.get(name, item["predicted_genre"])
        if genre not in KNOWN_GENRES and genre != "unknown":
            # 五类之外的体裁：允许，走通用提取策略
            print(f"提示：{name} 判为五类之外的体裁「{genre}」，使用通用提取策略。")
        final_genres[name] = genre

    print("体裁判定：")
    for item in plan:
        name = item["path"].name
        marker = "（LLM 确认）" if name in genre_overrides else "（启发式预判）"
        print(f"  {name} → {final_genres[name]} {marker}")
    print()

    if args.deep and len(docs) > DEEP_MODE_DOC_GUARD:
        print(
            f"⚠️  深度编译守卫：Inbox 中有 {len(docs)} 篇文档（>{DEEP_MODE_DOC_GUARD}），"
            "建议普通模式或逐篇深度编译；请与用户确认后继续。",
            file=sys.stderr,
        )

    ensure_buffer_dirs()

    units = build_compile_units(docs, max_chars=args.max_chars, genres=final_genres)
    print(f"生成 {len(units)} 个编译单元。")

    batches = group_batches(units, max_chars=args.max_chars, deep=args.deep)
    mode_label = "深度编译" if args.deep else "普通编译"
    print(f"{mode_label}：组织为 {len(batches)} 个批次，每批 ≤{args.max_chars} 字符且为同一体裁。\n")

    processed_sources = set()

    for idx, batch in enumerate(batches, 1):
        batch_chars = sum(u["char_count"] for u in batch)
        sources = {u["source_path"].name for u in batch}
        genre = batch[0].get("genre") or "generic"
        print(f"--- 批次 {idx}/{len(batches)}（体裁：{genre}） ---")
        print(f"来源：{', '.join(sources)}")
        print(f"编译单元数：{len(batch)}，总字数：{batch_chars}")

        prompt = format_batch_prompt(batch, genre=genre, deep=args.deep)

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

    print(f"\n=== /compile {mode_label}报告 ===")
    print(f"原始文档数：{len(docs)}")
    print(f"编译单元数：{len(units)}")
    print(f"批次数：{len(batches)}")
    genre_dist = {}
    for item in plan:
        g = final_genres[item["path"].name]
        genre_dist[g] = genre_dist.get(g, 0) + 1
    print("体裁分布：" + "，".join(f"{g}×{n}" for g, n in sorted(genre_dist.items())))
    if args.deep:
        print("深度编译：请在消化报告中说明每篇文档的维度覆盖度。")
    if not args.dry_run:
        print(f"已处理来源：{', '.join(p.name for p in processed_sources)}")
    print("==================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
