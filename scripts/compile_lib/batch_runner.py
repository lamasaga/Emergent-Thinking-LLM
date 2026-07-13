"""编译单元的批次组织、LLM 调用与 Buffer 写入。"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from compile_lib import BUFFER_DIR


COMPILE_SYSTEM_PROMPT = """你是一位个人知识库的编译助手。你的任务是将输入的原始文本进行原子化拆解，生成 Buffer 中间产物。

请遵循以下规则：
1. 提取值得保留的观察、立场、概念、方法、冲突、实体等碎片。
2. 为每个碎片指定一个暂定 type，必须从以下 10 个类型中选择：
   domain, notion, principle, phenomenon, entity, group, model, method, conflict, note。
3. 若无法判定 type，先放入 note。
4. 每个碎片单独输出为一个 YAML frontmatter + Markdown 正文块。
5. 禁止使用 [[ ]] 链接；提及已有概念时用加粗即可。
6. source 字段必须精确标注原始来源。
7. 宁可少拆，不要硬造；允许拆解不完整。
"""


def build_batches(units: list[dict], max_chars: int = 30000) -> list[list[dict]]:
    """将编译单元按 max_chars 上限分批。"""
    batches = []
    current = []
    current_chars = 0

    for unit in units:
        unit_chars = unit["char_count"]

        if unit_chars > max_chars:
            if current:
                batches.append(current)
                current = []
                current_chars = 0
            batches.append([unit])
            continue

        if current_chars + unit_chars > max_chars and current:
            batches.append(current)
            current = []
            current_chars = 0

        current.append(unit)
        current_chars += unit_chars

    if current:
        batches.append(current)

    return batches


def format_batch_prompt(units: list[dict]) -> str:
    """将一批编译单元格式化为给 LLM 的提示词。"""
    parts = [COMPILE_SYSTEM_PROMPT, "", f"本批共 {len(units)} 个片段，总字数约 {sum(u['char_count'] for u in units)}：", ""]

    for idx, unit in enumerate(units, 1):
        source_parts = [unit["source_path"].name, unit["title"]]
        if unit.get("section"):
            source_parts.append(unit["section"])
        if unit.get("page_range"):
            source_parts.append(f"p.{unit['page_range']}")
        source = " / ".join(source_parts)

        parts.append("---")
        parts.append(f"片段 {idx}/{len(units)}")
        parts.append(f"source: {source}")
        parts.append(f"char_count: {unit['char_count']}")
        parts.append("---")
        parts.append(unit["text"])
        parts.append("")

    return "\n".join(parts)


def parse_llm_buffers(raw_output: str, default_source: str) -> list[dict]:
    """
    解析 LLM 输出中的 Buffer 块。
    每个 Buffer 块格式：
    ---
    title: xxx
    type: xxx
    source: xxx
    ---
    # xxx
    ...
    """
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*?)(?=\n---\s*\n|$)", re.DOTALL | re.MULTILINE)
    buffers = []
    for fm, body in pattern.findall(raw_output):
        title = _extract_fm_field(fm, "title") or "未命名碎片"
        btype = _extract_fm_field(fm, "type") or "note"
        source = _extract_fm_field(fm, "source") or default_source
        buffers.append({
            "title": title,
            "type": btype,
            "source": source,
            "body": body.strip(),
        })
    return buffers


def _extract_fm_field(fm_text: str, field: str) -> str | None:
    m = re.search(rf"^{field}:\s*(.+?)$", fm_text, re.MULTILINE)
    return m.group(1).strip().strip('"').strip("'") if m else None


def _sanitize_filename(title: str) -> str:
    """将标题转换为合法文件名片段。"""
    s = re.sub(r"[<>:/\\|?*\"'\n]", "", title)
    s = s.strip().replace(" ", "-")
    return s[:50] or "untitled"


def write_buffer(buffer: dict, subtype: str) -> Path:
    """写入单个 Buffer 文件。"""
    now = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    safe_title = _sanitize_filename(buffer["title"])
    filename = f"{now}-{safe_title}.md"
    target_dir = BUFFER_DIR / subtype
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    frontmatter = f"""---
title: "{buffer['title']}"
type: "{buffer['type']}"
created: "{datetime.now().strftime('%Y-%m-%d')}"
updated: "{datetime.now().strftime('%Y-%m-%d')}"
source: "{buffer['source']}"
status: scratch
---

{buffer['body']}
"""
    target.write_text(frontmatter, encoding="utf-8")
    return target


def run_batch(batch: list[dict]) -> list[Path]:
    """处理一个批次：生成 prompt、调用 LLM、解析并写入 Buffer。"""
    prompt = format_batch_prompt(batch)
    # 注意：当前 Kimi Code CLI 环境中 LLM 调用由 agent 执行，
    # 因此 run_batch 仅组织 prompt；实际调用见 compile_loop.py。
    raise NotImplementedError("run_batch 需要接入实际 LLM 调用逻辑")


def check_digest_trigger() -> bool:
    """调用现有脚本检查是否达到 digest 阈值。"""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "check_digest_trigger.py")],
        capture_output=True,
        text=True,
    )
    return result.returncode != 0


def validate_buffers() -> bool:
    """调用现有脚本校验 Buffer。"""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "validate_buffer.py")],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
