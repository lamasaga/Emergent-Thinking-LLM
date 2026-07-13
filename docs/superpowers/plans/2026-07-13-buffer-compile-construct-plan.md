# Buffer、/compile 与合并 /construct 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: 由于本次变更以文档和目录结构为主，计划中的任务均为验证性任务，无需额外编码。

**Goal:** 将设计文档 `docs/superpowers/specs/2026-07-13-buffer-compile-construct-design.md` 落地为可操作的仓库结构：新增 `05-Buffer/` 缓冲层、更新 `AGENTS.md` 与 `ontology.md`、把变更推送到 GitHub。

**Architecture:** 通过 `/compile` 把 `00-Inbox/` 的 raw 文档原子化为 `05-Buffer/` 中的临时片段；`/digest` 只消费 `status: scratch` 的片段；`/construct` 读取全部 Buffer 与全部卡片，整体重组领域与结构。所有变更以文档和目录形式呈现，不涉及新的运行时服务。

**Tech Stack:** Markdown、Git、Python 3.13（仅用于现有 `scripts/validate_cards.py` 校验）。

---

### Task 1: 验证 AGENTS.md 已升级到 v3.2

**Files:**
- Read: `AGENTS.md`

- [ ] **Step 1: 检查版本号**

确认文件顶部标题为 `# AGENTS.md — AI 操作手册（v3.2）`，末尾版本声明为 `版本：v3.2`。

- [ ] **Step 2: 检查新增 /compile 指令**

搜索 `### 2.1 /compile`，确认存在该小节，并包含：触发条件、执行步骤、约束。

- [ ] **Step 3: 检查 /construct 已合并 /refactor**

搜索 `/refactor`（/重构）已合并进 `/construct`，并确认存在「`/refactor` 已合并进 `/construct`」的说明。

- [ ] **Step 4: 检查 /digest 调整**

确认 `/digest` 执行步骤中步骤 1 为「读取 05-Buffer/ 中 status: scratch 的文件」，步骤 10 为标记 Buffer 为 `digested`。

---

### Task 2: 验证 ontology.md 已声明 Buffer 规则

**Files:**
- Read: `01-Cards/_meta/ontology.md`

- [ ] **Step 1: 检查 Buffer 目录与元数据章节**

确认存在 `## Buffer 目录与元数据` 小节，包含：
- `05-Buffer/` 用途说明
- 10 个 type 子目录名称
- 文件命名格式 `YYYY-MM-DD-HHMMSS-关键词.md`
- `status: scratch | digested | constructed` 说明
- Buffer 不使用 `[[ ]]` 链接的规则

- [ ] **Step 2: 检查 updated 日期**

确认 frontmatter 中的 `updated` 字段为 `2026-07-13`。

---

### Task 3: 验证 05-Buffer/ 目录结构

**Files:**
- List: `05-Buffer/`

- [ ] **Step 1: 检查子目录**

确认存在以下 10 个子目录，且每个目录下都有 `.gitkeep`：

```
domain/
notion/
principle/
phenomenon/
entity/
group/
model/
method/
conflict/
note/
```

- [ ] **Step 2: 检查 README.md**

确认 `05-Buffer/README.md` 包含：
- 目录说明
- 文件命名示例
- frontmatter 模板
- 使用规则
- status 含义

---

### Task 4: 运行现有校验脚本

**Files:**
- Run: `scripts/validate_cards.py`

- [ ] **Step 1: 执行校验**

命令：

```bash
C:/Users/MECHREVO/AppData/Local/Programs/Python/Python313/python.exe scripts/validate_cards.py
```

- [ ] **Step 2: 确认通过**

预期输出：

```
✅ 所有卡片检查通过
```

说明：当前 `01-Cards/` 尚无卡片，脚本应通过；若未来有卡片，需保证新增卡片符合规范。

---

### Task 5: 提交并推送到 GitHub

**Files:**
- Add: `AGENTS.md`、`01-Cards/_meta/ontology.md`、`05-Buffer/`、`docs/superpowers/specs/2026-07-13-buffer-compile-construct-design.md`

- [ ] **Step 1: 暂存变更**

```bash
git add AGENTS.md 01-Cards/_meta/ontology.md 05-Buffer/
git add -f docs/superpowers/specs/2026-07-13-buffer-compile-construct-design.md
```

- [ ] **Step 2: 提交**

```bash
git commit -m "feat: add Buffer layer, /compile command, merge /construct and /refactor"
```

- [ ] **Step 3: 推送**

```bash
git push origin 涌现中介
```

预期输出：

```
To https://github.com/lamasaga/Emergent-Thinking-LLM.git
   ...  涌现中介 -> 涌现中介
```

---

## 自检

- [x] Spec coverage：设计文档中的每个章节（工作流、Buffer 规范、三个指令、Token 优化、hooks 协作）都已对应到目录、文档或校验动作。
- [x] Placeholder scan：计划中没有 TBD、TODO、"实现 later" 等占位符。
- [x] Type consistency：Buffer 状态值 `scratch | digested | constructed` 与 AGENTS.md、ontology.md、README.md 保持一致。

---

## 备注

本次变更不引入新的代码模块或运行时依赖。未来若 Buffer 规模扩大，可在此基础上新增：
- `scripts/compile_to_buffer.py`：将 `/compile` 中的确定性工作（文件创建、归档移动）从 LLM 中抽离。
- Buffer 命名与 status 校验 hook。
- `_index.md` 或 `/compress` 机制以进一步降低 `/construct` 的 token 消耗。
