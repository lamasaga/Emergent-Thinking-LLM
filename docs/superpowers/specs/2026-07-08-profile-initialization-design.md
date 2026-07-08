---
id: "profile-initialization-design"
title: "Profile 初始化与增量更新设计"
type: "design-spec"
created: "2026-07-08"
updated: "2026-07-08"
status: "draft"
---

# Profile 初始化与增量更新设计

## 背景与问题

当前 `AGENTS.md` 的 `/construct` 流程只负责生成 `01-Cards/` 的领域卡片、实例卡片和 `ontology.md`，完全没有初始化 `02-Profile/` 的步骤。结果是：

- `02-Profile/` 的四个文件（`profile-index.md`、`语言风格.md`、`思维模型.md`、`核心信念.md`）虽然存在，但内容几乎都是空模板，使用 `（待 /digest 根据内容填充）` 占位。
- `/digest` 只有在“检测到新模式或信念变化”时才更新 Profile，但 Profile 初始为空，后续触发条件模糊，导致 Profile 长期闲置。
- `/analyze` 在分析前会读取 Profile，但空 Profile 无法提供“用户是谁”的透镜作用。

## 目标

让 `/construct` 在建构阶段就基于种子文章为 `02-Profile/` 搭建出有依据、可追踪、结构化的基础框架；让 `/digest` 在此基础上进行增量迭代，形成“建构生骨架、消化长血肉”的完整闭环。

## 设计决策

1. **种子内容直接写入主 Profile 文件**：`/construct` 不再把 Profile 留给后续填补，而是从 `00-Inbox/` 的种子文档中直接提炼语言风格、思维模型、核心信念的初稿，写入对应的 Profile 文件。
2. **状态分层**：初稿标记为 `seed`，经 `/digest` 多次验证或用户确认后可升级为 `growing`/`mature`。
3. **来源强制标注**：Profile 中的每条推断、每个摘录都必须标注来源，避免 AI 幻觉。
4. **确认 gate 不变**：`/digest` 对 Profile 的任何修改仍需先向用户报告变更点，经确认后写入，保留现有安全边界。

## 详细设计

### 1. 修改 `/construct` 流程

在 `AGENTS.md` `/construct` 现有第 6 步“更新 ontology.md”之后，新增第 7 步：

```
7. 基于种子内容生成 02-Profile/ 初稿
   a. 重新扫描 00-Inbox/ 中的种子文档。
   b. 分别提炼并写入：
      - 02-Profile/语言风格.md：常用句式/修辞、术语偏好、段落节奏、引用习惯、原文摘录
      - 02-Profile/思维模型.md：常用分析框架、演绎/归纳/类比/反证模式、默认解决路径、原文摘录
      - 02-Profile/核心信念.md：根本立场、明确反对、认为最重要、原文摘录
   c. 每条推断必须标注来源（文件名或具体引用）。
   d. 在 02-Profile/profile-index.md 中记录版本历史。
   e. 若某栏目种子内容不足，保留结构化空槽并标记为 awaiting-content，不编造内容。
```

新增约束：

- `/construct` 生成的 Profile 条目 frontmatter `status: seed`。
- 每个 Profile 文件的原文摘录总数 ≤ 10 条。
- `/construct` 禁止通过读取全部卡片来反推 Profile，只能基于种子文档和已生成的领域/实例卡片进行主题聚焦。

### 2. 修改 `/digest` 流程

保留 `/digest` 第 7 步“评估对 02-Profile/ 的影响”，并细化为：

```
7. 评估对 02-Profile/ 的影响：
   a. 读取当前 02-Profile/ 全部文件。
   b. 对比新内容与现有条目：
      - 是否出现新的语言风格/句式？→ 向用户报告，确认后追加到 语言风格.md
      - 是否使用新的思维模型/推理模式？→ 确认后追加到 思维模型.md
      - 是否表达新的核心信念或立场变化？→ 确认后追加/修订 核心信念.md
   c. 当某 Profile 文件积累了 ≥3 个不同来源的支持证据，或用户明确确认时，
      将 frontmatter status 从 seed 升级为 growing。
   d. 若原文摘录超过 10 条上限，向用户报告并请求替换决策。
   e. 更新 profile-index.md 版本历史。
```

### 3. Profile 文件模板与状态规范

每个 Profile 文件内部按栏目标注状态与来源，例如 `02-Profile/语言风格.md`：

```markdown
## 常用句式与修辞
> 本节状态：seed（由 /construct 从种子内容初步归纳）

- 喜欢使用“……不是……，而是……”的对比句式
  - 来源：[[00-Inbox/种子文章.md]]
```

`02-Profile/profile-index.md` 增加“Profile 演化日志”：

```markdown
## Profile 演化日志

| 日期 | 触发指令 | 变更文件 | 变更摘要 |
|---|---|---|---|
| 2026-07-08 | /construct | 语言风格.md、思维模型.md、核心信念.md | 从种子文章生成初稿 |
```

### 4. 同步更新 AGENTS.md 与 README.md

- 在 `AGENTS.md` 的 `/construct` 步骤和约束中加入 Profile 初始化。
- 在 `/digest` 步骤中加入 Profile 升级规则与确认流程。
- 在 `README.md` 的目录结构和工作流图中，把 Profile 初始化加入 `/construct` 的输出。

### 5. 边界与错误处理

- **种子不足**：若 `00-Inbox/` 为空或内容太少，`/construct` 仍生成结构化模板，但推断区标记为 `awaiting-content`，不虚构。
- **不越权覆盖**：`/digest` 对 Profile 的任何写入仍需用户确认，保持现有禁止事项。
- **来源可追踪**：所有 Profile 条目必须有 `来源：` 标注。
- **引用上限**：原文摘录超过 10 条时，AI 不得自动删除，必须向用户报告并请求替换决策。

## 涉及文件

- `AGENTS.md`
- `README.md`
- `02-Profile/profile-index.md`
- `02-Profile/语言风格.md`
- `02-Profile/思维模型.md`
- `02-Profile/核心信念.md`

## 验证方式

1. 检查 `AGENTS.md` 的 `/construct` 与 `/digest` 步骤是否准确反映了上述设计。
2. 检查 `02-Profile/` 模板是否包含状态标注、来源标注、原文摘录区和演化日志。
3. 进行一次模拟的 `/construct` 说明，确认流程可执行、无歧义。
