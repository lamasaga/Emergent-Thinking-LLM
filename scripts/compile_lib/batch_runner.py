"""编译单元的批次组织、LLM 调用与 Buffer 写入。"""

import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

from compile_lib import BUFFER_DIR


logger = logging.getLogger(__name__)


VALID_BUFFER_TYPES = {
    "domain", "notion", "principle", "phenomenon", "entity",
    "group", "model", "method", "conflict", "note",
}

# 分体裁提取策略的公共输出规则
_FORMAT_RULES = """请遵循以下输出规则：
1. 每个碎片单独输出为一个 YAML frontmatter + Markdown 正文块。
2. 为每个碎片指定一个暂定 type，必须从以下 10 个类型中选择：
   domain, notion, principle, phenomenon, entity, group, model, method, conflict, note。
   若无法判定 type，先放入 note。
3. 禁止使用 [[ ]] 链接；提及已有概念时用加粗即可。
4. source 字段必须精确标注原始来源。
5. frontmatter 增加 genre 字段（来源体裁）；涉及作者本人作品时增加 perspective: self，外部作品为 perspective: external。
6. 宁可少拆，不要硬造；允许拆解不完整。"""

# 学术九维提取说明（论文/图书/通用策略共用）
_ACADEMIC_DIMENSIONS = """从以下维度提取原子碎片，每个维度独立成块：
a. problem：核心问题、研究动机。
b. claim：作者核心主张、立场、结论性判断。
c. model：提出的模型/框架/解释结构，含关键组件与关系。
d. method：方法/流程/实现细节，含输入、步骤、输出。
e. evidence：实验/证据/评测，含数据集、指标、结果、与基线的对比。
f. limit：限制、代价、未解决问题、适用范围边界。
g. conflict：与现有工作、常识或本知识库已有观点的张力。
h. connection：与其他文档、已知概念的潜在关联假设。
i. quote：值得保留的原文摘录（≤3 条/碎片），必须标注页码/章节。"""

GENRE_PROMPTS = {
    "book": f"""你是一位个人知识库的编译助手。当前材料体裁为【图书】。

按目录章节切分的文本将逐单元提供。请深度拆解：
{_ACADEMIC_DIMENSIONS}

图书特有要求：
- 重点关注 model 维度：章节间关系与全书论证主线。
- 额外产出 1 个「全书结构」碎片（type: model 或 note），概括论证主线与章节骨架。
- 来源锚点精确到「第 X 章 / 第 X 页」。

{_FORMAT_RULES}""",

    "paper": f"""你是一位个人知识库的编译助手。当前材料体裁为【论文】。

{_ACADEMIC_DIMENSIONS}

论文特有要求：
- evidence 碎片必须含数据集、指标、与基线对比。
- 来源锚点精确到 arXiv ID / DOI / 图表编号。

{_FORMAT_RULES}""",

    "essay": f"""你是一位个人知识库的编译助手。当前材料体裁为【随笔】，默认是用户本人的思想素材。

目标不是「内容摘要」，而是「思想建模」。从以下维度提取原子碎片：
a. stance：核心立场与判断。
b. reasoning：推理路径——作者怎么想的，而不只是想的是什么。
c. notion/model：提出的概念或心智模型。
d. experience：作为论据的个人经历与观察。
e. style：语言风格线索（标志性句式、修辞、术语偏好）。
f. tension：犹豫、自相矛盾、未解决的纠结。
g. quote：原文摘录（≤3 条/碎片）。

随笔特有要求：
- style/reasoning/tension 类碎片是 02-Profile 的直接种子素材，提取优先级最高。
- 区分作者原意与编译者的解读。

{_FORMAT_RULES}""",

    "dialogue": f"""你是一位个人知识库的编译助手。当前材料体裁为【对话录】，默认涉及用户本人。

对话是思维过程的直接证据，推理模式提取优先于结论提取。从以下维度提取原子碎片：
a. stance：每个说话人的立场及观点演变（标注说话人）。
b. turn：思维转折点——什么改变/推进了想法。
c. disagreement：分歧与未解决冲突 → conflict 碎片。
d. consensus：达成的共识。
e. question：被提出但未回答的好问题。
f. style：用户本人的表达风格线索。
g. quote：原话摘录，正文必须标注说话人。

对话录特有要求：
- 若输入文本按轮次切分，可在话题转折点调整边界，但不得丢失说话人标签。
- quote 碎片正文必须带说话人名。

{_FORMAT_RULES}""",

    "scrap": f"""你是一位个人知识库的编译助手。当前材料体裁为【零散材料】。

轻量提取，每条想法/每篇短文档产出 1-3 个碎片即可：
a. core：想法内核。
b. context：记录背景（若可推断，标注为推断）。
c. connection：潜在关联假设。
d. quote：原文摘录。

零散材料特有要求：
- 价值在「种子」不在「完整」；禁止为凑数把一句话硬拆成多个碎片。
- 多篇短文档合并提供时，每个碎片独立归属其来源文档。

{_FORMAT_RULES}""",

    "generic": f"""你是一位个人知识库的编译助手。你的任务是将输入的原始文本进行原子化拆解，生成 Buffer 中间产物。

{_ACADEMIC_DIMENSIONS}

{_FORMAT_RULES}""",
}

# 深度编译模式附加指令
DEEP_MODE_SUFFIX = """

【深度编译模式】
- 碎片数量不设上限，按信息密度榨取；但仍禁止硬造碎片。
- 多遍扫描：先主线/结构，再逐节深挖，最后横向挖掘（冲突、关联、风格线索）。
- 每条碎片含更完整上下文，可多条摘录，并与同文档其他碎片形成指涉链。
- 体裁深挖项：论文加图表/公式/实验设计细节；图书加逐章要点与概念谱系；
  随笔逐段挖 reasoning/style/tension；对话录加观点演变弧线；零散材料补背景重构。
- 输出末尾附维度覆盖度说明：哪些维度有产出、哪些没有及原因。"""

# 兼容旧引用
COMPILE_SYSTEM_PROMPT = GENRE_PROMPTS["generic"]


def get_genre_prompt(genre: str | None, deep: bool = False) -> str:
    """获取体裁对应的 system prompt；未知体裁回退到 generic。"""
    prompt = GENRE_PROMPTS.get(genre or "", GENRE_PROMPTS["generic"])
    if deep:
        prompt += DEEP_MODE_SUFFIX
    return prompt


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


def format_batch_prompt(
    units: list[dict],
    genre: str | None = None,
    deep: bool = False,
) -> str:
    """将一批编译单元格式化为给 LLM 的提示词，按体裁使用对应提取策略。"""
    if genre is None and units:
        genre = units[0].get("genre")
    system_prompt = get_genre_prompt(genre, deep=deep)

    parts = [system_prompt, "", f"本批共 {len(units)} 个片段，总字数约 {sum(u['char_count'] for u in units)}：", ""]

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
    支持 ```yaml ... ``` 代码围栏。
    每个 Buffer 块格式：
    ---
    title: xxx
    type: xxx
    source: xxx
    ---
    # xxx
    ...
    """
    # 去除可能的 markdown 代码围栏
    text = raw_output.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
        text = text.strip()

    if not text:
        raise ValueError("LLM 输出为空")

    buffers = []
    pos = 0
    while True:
        # 查找下一个 frontmatter 起点
        start = text.find("---", pos)
        if start == -1:
            break
        # 查找 frontmatter 终点
        end = text.find("---", start + 3)
        if end == -1:
            break
        fm_text = text[start + 3:end].strip()

        try:
            fm = yaml.safe_load(fm_text)
            if not isinstance(fm, dict):
                raise ValueError("frontmatter 不是字典")
        except yaml.YAMLError as e:
            logger.warning("解析 frontmatter 失败：%s", e)
            pos = end + 3
            continue

        # 正文：从 end+3 到下一个真实 frontmatter 起点
        # 允许正文中包含 ---，只有紧随合法 frontmatter 的 --- 才视为下一块起点
        candidate = text.find("---", end + 3)
        next_start = -1
        while candidate != -1:
            fm_end_candidate = text.find("---", candidate + 3)
            if fm_end_candidate == -1:
                break
            candidate_fm_text = text[candidate + 3:fm_end_candidate].strip()
            try:
                candidate_fm = yaml.safe_load(candidate_fm_text)
                if isinstance(candidate_fm, dict) and "title" in candidate_fm:
                    next_start = candidate
                    break
            except yaml.YAMLError:
                pass
            candidate = text.find("---", candidate + 3)

        body = text[end + 3:next_start if next_start != -1 else len(text)].strip()

        btype = fm.get("type", "note")
        if btype not in VALID_BUFFER_TYPES:
            logger.warning("非法 Buffer type '%s'，回退到 note", btype)
            btype = "note"

        buffers.append({
            "title": str(fm.get("title", "未命名碎片")),
            "type": btype,
            "source": str(fm.get("source", default_source)),
            "genre": str(fm["genre"]) if fm.get("genre") else None,
            "perspective": (
                str(fm["perspective"]) if fm.get("perspective") else None
            ),
            "body": body,
        })

        pos = end + 3
        if next_start == -1:
            break

    if not buffers:
        raise ValueError("未从 LLM 输出中解析到任何 Buffer 块")

    return buffers


def _sanitize_filename(title: str) -> str:
    """将标题转换为合法文件名片段。"""
    s = re.sub(r"[<>:/\\|?*\"'\n]", "", title)
    s = s.strip().replace(" ", "-")
    return s[:50] or "untitled"


def write_buffer(buffer: dict, subtype: str, now: datetime | None = None) -> Path:
    """写入单个 Buffer 文件。"""
    if now is None:
        now = datetime.now()

    btype = buffer.get("type", "note")
    if btype not in VALID_BUFFER_TYPES:
        logging.warning("非法 Buffer type '%s'，回退到 note", btype)
        btype = "note"
    if subtype not in VALID_BUFFER_TYPES:
        subtype = "note"

    safe_title = _sanitize_filename(buffer["title"])
    filename = now.strftime(f"%Y-%m-%d-%H%M%S-%f-{safe_title}.md")
    target_dir = BUFFER_DIR / subtype
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    frontmatter = {
        "title": buffer["title"],
        "type": btype,
        "created": now.strftime("%Y-%m-%d"),
        "updated": now.strftime("%Y-%m-%d"),
        "source": buffer["source"],
        "status": "scratch",
    }
    # 可选字段：来源体裁与作者视角（供 /digest 判断消费方式）
    if buffer.get("genre"):
        frontmatter["genre"] = buffer["genre"]
    if buffer.get("perspective"):
        frontmatter["perspective"] = buffer["perspective"]
    content = "---\n" + yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False) + "---\n\n" + buffer["body"]
    target.write_text(content, encoding="utf-8")
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
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode != 0


def validate_buffers() -> bool:
    """调用现有脚本校验 Buffer。"""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent.parent / "validate_buffer.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0
