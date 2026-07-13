# 设计文档：Buffer、/compile 与合并后的 /construct

> 日期：2026-07-13
> 版本：v1.0
> 关联文件：`AGENTS.md` v3.2、`ontology.md`

---

## 1. 背景与目标

个人思想建模系统从「一次消化一篇文章」升级为「编译 → 缓冲 → 建构/消化」的流水线：

- **编译（/compile）** 把 raw 文档拆解成原子化、可反复加工的中间产物。
- **缓冲（05-Buffer/）** 承载这些中间产物，按 ontology 类型分目录，按时间排序。
- **建构（/construct）** 从全部 Buffer 中整体涌现领域、卡片结构与 Profile。
- **消化（/digest）** 只处理未被消费过的 Buffer，对现有卡片做增量更新。

目标是在保持颗粒度的同时，降低 `/digest` 的重复 token 消耗，并让 `/construct` 拥有对整个 `01-Cards/` 编排的掌控力。

---

## 2. 总体工作流

```
00-Inbox/raw 文档
        │
        ▼
    /compile ──────► 05-Buffer/<type>/YYYY-MM-DD-HHMMSS-关键词.md
        │                  status: scratch
        │                       │
        │                       ▼
   03-Archive/            /digest（增量）
   （原始文档归档）          只读 status: scratch
                            丰富/新建卡片
                            标记为 status: digested
                            更新 Profile（需用户确认）
                                 │
                                 ▼
                          /construct（整体建构/重组）
                          读取全部 Buffer（scratch/digested/constructed）
                          读取全部卡片与领域
                          提出整体结构方案 → 用户确认
                          执行：新建/合并/拆分/移动/调整领域
                          更新 ontology.md
                          标记被整合的 Buffer 为 status: constructed
```

`/refactor` 已合并进 `/construct`，原 `/refactor` 指令标记为 deprecated。

---

## 3. 05-Buffer/ 目录结构

```
05-Buffer/
├── README.md
├── domain/
├── notion/
├── principle/
├── phenomenon/
├── entity/
├── group/
├── model/
├── method/
├── conflict/
└── note/
```

- 子目录直接复用 `ontology.md` 中的 10 个 type 名称，保持与卡片类型体系同构。
- 每个类型目录内部按文件名字母顺序排列，即按时间顺序排列。

### 3.1 文件命名

```
YYYY-MM-DD-HHMMSS-关键词.md
```

示例：

- `05-Buffer/notion/2026-07-13-093625-学习是结构生成.md`
- `05-Buffer/conflict/2026-07-13-094200-脚手架与自主的张力.md`

### 3.2 frontmatter 规范

```yaml
---
title: "学习是结构生成"
type: "notion"
created: "2026-07-13T09:36:25"
updated: "2026-07-13T09:36:25"
source: "《某书》第3章"
status: "scratch"   # scratch | digested | constructed
---
```

- 不写 `id`，不写 `relations`。
- `status` 允许被 `/digest` 或 `/construct` 更新，`updated` 同步更新。
- 正文内容严格单次写入，创建后不再修改。

### 3.3 status 含义

| status | 含义 | 谁写入 |
|--------|------|--------|
| `scratch` | 刚由 `/compile` 生成，尚未被消费 | `/compile` |
| `digested` | 已被 `/digest` 处理过，不再进入后续 `/digest` | `/digest` |
| `constructed` | 已被 `/construct` 整合进整体结构，不再进入 `/digest`，但仍可被下一次 `/construct` 读取 | `/construct` |

### 3.4 链接规则

- Buffer 文件**不使用 `[[ ]]`**。
- 提及已有卡片时用 **加粗** 或纯文本，例如「**认知脚手架**」「双系统模型」。
- 这样可以避免幽灵链接治理问题，也让 Buffer 保持「草稿」身份。

---

## 4. /compile 指令

### 4.1 触发条件

用户在 `00-Inbox/` 中放入 raw 文档后，主动说 `/compile`。

### 4.2 执行步骤

1. 读取 `00-Inbox/` 下全部文件。
2. 对每篇 raw 文档进行原子化拆解：
   - 提取观察、立场、概念、方法、冲突、实体等碎片。
   - 为每个碎片指定一个暂定 `type`（来自 ontology.md 的 10 个类型）。
   - 无法判定 type 时，先放入 `note/`。
3. 将每个碎片写入 `05-Buffer/<type>/YYYY-MM-DD-HHMMSS-关键词.md`：
   - `status: scratch`
   - 不写 `id`，不写 `relations`，不使用 `[[ ]]`。
4. 输出编译报告：Buffer 文件数量、各类型分布、无法归类片段数量、潜在高价值主题提示。
5. 将原始文档移动到 `03-Archive/`。

### 4.3 约束

- 只生成 Buffer，不创建/修改 `01-Cards/` 或 `02-Profile/`。
- 不建立幽灵链接。
- 一个碎片一文件，正文单次写入。
- 拆解允许不完整；宁可少拆，不要硬造。

---

## 5. /digest 指令

### 5.1 触发条件

`05-Buffer/` 中有 `status: scratch` 的文件，或用户主动说 `/digest`。

### 5.2 读取范围

- `05-Buffer/` 中 `status: scratch` 的文件。
- `01-Cards/_meta/ontology.md`。
- `01-Cards/domains/` 全部领域卡片。
- 与 scratch Buffer 相关的领域卡片指向的实例卡片。
- 当前 `02-Profile/` 全部文件。

### 5.3 执行步骤

1. 读取所有 `status: scratch` 的 Buffer。
2. 判断涉及哪些领域，读取相关实例卡片。
3. 进行比较分析：
   - 概念/模型/方法是否已有卡片？
     - 有：丰富卡片，更新 `sources` 和 `updated`。
     - 无：判断是否重要且持久，决定是否新建。
   - 内容与现有卡片是否冲突？
     - 是：标记冲突，考虑新建冲突卡片。
   - 实体是否已有卡片？
     - 有：补充信息。
     - 无：判断重要性后决定是否新建。
4. 检查目录结构是否需要调整，必要时更新 `ontology.md`。
5. 评估对 `02-Profile/` 的影响：
   - 检测语言风格、思维模型、核心信念的新模式。
   - 向用户报告变更点，**经确认后写入**。
   - 在 `profile-index.md` 追加版本历史。
6. 更新领域卡片。
7. 将本次读取的所有 scratch Buffer 的 `status` 改为 `digested`，并更新 `updated`。
8. 输出消化报告。

### 5.4 约束

- 不删除、不移动 Buffer 文件。
- Profile 更新前必须报告并获确认。
- 遵循实例引用上限：cards ≤ 6，profile ≤ 10。
- 禁止幽灵链接。

---

## 6. /construct 指令（已合并 /refactor）

### 6.1 触发条件

- 用户主动说 `/construct`。
- `/digest` 报告指出存在需要整体重组的结构张力。
- 用户想从 Buffer 中重新涌现领域和思维结构。

### 6.2 读取范围

- `05-Buffer/` 中**全部**文件（scratch + digested + constructed）。
- `01-Cards/_meta/ontology.md`。
- `01-Cards/domains/` 全部领域卡片。
- 全部或相关范围内的实例卡片。
- 当前 `02-Profile/` 全部文件。

### 6.3 执行步骤

1. 读取全部 Buffer 和现有卡片结构。
2. 识别核心主题、跨领域概念、冲突、模型、方法、实体。
3. 识别结构信号：
   - 冗余：两张及以上卡片核心主张/定义/实例高度重叠。
   - 分裂：一张卡片包含多个可独立回答的问题，或跨多个领域。
   - 链接空洞：高相关卡片缺少显式 relations，或出现孤岛。
   - 链接过载：单张卡片 outgoing relations 超过 6 条。
   - 类型错配：卡片实际内容与 `type` 不一致。
   - 目录张力：领域目录无法容纳新卡片群，或某目录过于膨胀。
   - Buffer 聚集：某一类型目录大量堆积，暗示该类型缺乏清晰卡片承接。
   - 概念漂移：Buffer 中对同一关键词的描述与卡片定义出现分歧。
   - 领域边界：Buffer 中反复出现跨当前多个领域的碎片，提示需要新建/合并领域。
   - 幽灵链接或断裂关系。
4. 提出 1-3 个整体结构方案，包含诊断、动作、影响范围、风险。
5. **向用户呈现方案并获确认**。涉及 Profile 修改时单独报告并确认。
6. 执行方案：
   - 新建/调整领域卡片。
   - 新建/合并/拆分/废弃实例卡片。
   - 调整目录结构。
   - 增删或修改 frontmatter relations 与正文 `[[id|显示文本]]`。
   - 修正卡片 `type`。
   - 清理幽灵链接。
   - 更新 `ontology.md`。
   - 如需，更新 `02-Profile/`。
7. 更新所有受影响卡片的 `updated`。
8. 将已整合进结构的 Buffer 文件标记为 `status: constructed`，更新 `updated`。
9. 输出建构报告。

### 6.4 约束

- 禁止删除任何卡片；合并后的原卡片标记为 `status: deprecated`，并保留指向主卡片的链接。
- 合并/拆分卡片时，必须在相关卡片中记录历史沿革和原因。
- 所有新增、修改、删除的链接必须保证无幽灵链接。
- 每次 `/construct` 必须更新 `ontology.md` 的结构变更记录。
- 涉及 `02-Profile/` 修改需单独获得用户确认。
- `/construct` 可以反复调用，不限于项目初期。

---

## 7. /refactor 的处理

`/refactor` 标记为 **deprecated**，其功能由 `/construct` 完全覆盖。当用户说 `/refactor` 时，AI 提示其已合并到 `/construct`，并询问是否继续以 `/construct` 执行。

---

## 8. /analyze 边界

保持原逻辑：读取 `02-Profile/`、`ontology.md`、相关领域与实例卡片，组装 Context Package 到 `04-OutBox/`。

当用户问题明显涉及近期原始动机时，可**选择性**读取 `05-Buffer/` 中的 `scratch` 文件作为补充上下文，但不强制。

---

## 9. Token 优化策略

- `/digest` 只读 `status: scratch` 的文件，token 消耗随新增未处理素材增长，不随历史累积。
- `/construct` 读全部 Buffer，但它是低频、整体性的操作，且需要用户确认。
- 如果未来 Buffer 历史过大，可再引入 `/compress` 或 `_index.md` 作为第二层优化；当前先用状态标记解决主要问题。

---

## 10. 与 hooks 的协作

| 指令 | hooks 承担的确定性工作 | LLM 承担的语义工作 |
|------|----------------------|-------------------|
| `/compile` | 输入文件存在性检查、Buffer 命名规范校验、原始文档归档移动 | raw 文本的原子化拆解、暂定类型判断 |
| `/construct` | 目录创建、frontmatter 模板校验、id 唯一性检查、结构信号扫描 | 主题识别、领域设计、整体重组方案、Profile 更新 |
| `/digest` | frontmatter 补全、`updated` 字段更新、实例/引用上限检查 | 概念匹配、冲突检测、新建/丰富判断、Profile 变更报告 |
| `/analyze` | Context Package 格式校验、输出文件命名、引用列表提取 | 推理、论证、风格化表达 |

`scripts/validate_cards.py` 仍只扫描 `01-Cards/`，`05-Buffer/` 不受卡片规则约束。

---

## 11. 文件变更清单

- 新增 `docs/superpowers/specs/2026-07-13-buffer-compile-construct-design.md`（本文件）。
- 新增 `05-Buffer/` 目录结构与 `README.md`。
- 修改 `AGENTS.md`：加入 `/compile`、合并 `/construct` 与 `/refactor`、调整 `/digest`、声明 `/refactor` deprecated。
- 修改 `ontology.md`：声明 `05-Buffer/` 目录与 Buffer 元数据规则。
