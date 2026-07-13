# 05-Buffer / 缓冲层

这是 raw 文档与 `01-Cards/` 卡片之间的中间层，用来存放由 `/compile` 生成的原子化片段。

## 目录说明

子目录对应 `ontology.md` 中的 10 个类型：

- `domain/` — 领域性观察
- `notion/` — 观念、立场、信条
- `principle/` — 原则、原理、规律
- `phenomenon/` — 现象、模式、趋势
- `entity/` — 有明确边界的实体对象
- `group/` — 多个实体构成的群体
- `model/` — 模型、框架、解释结构
- `method/` — 方法、技巧、流程
- `conflict/` — 冲突、张力、两难
- `note/` — 暂时无法归类的想法

## 文件命名

```
YYYY-MM-DD-HHMMSS-关键词.md
```

示例：`notion/2026-07-13-093625-学习是结构生成.md`

## frontmatter 模板

```yaml
---
title: ""
type: ""
created: "2026-07-13T09:36:25"
updated: "2026-07-13T09:36:25"
source: ""
status: "scratch"   # scratch | digested | constructed
---
```

## 使用规则

1. **正文单次写入**：创建后不再修改正文内容。
2. **状态可更新**：`status` 与 `updated` 可由 `/digest` 或 `/construct` 更新。
3. **不建立 `[[ ]]` 链接**：提及已有卡片用 **加粗** 或纯文本。
4. **一文件一想法**：尽量保持原子化，方便后续迁移到 `01-Cards/`。
5. **手动清理**：当某个片段已被吸收进卡片后，可手动删除或移动到 `03-Archive/`。

## 状态含义

- `scratch`：刚由 `/compile` 生成，尚未被消费。
- `digested`：已被 `/digest` 处理过，不再进入后续 `/digest`。
- `constructed`：已被 `/construct` 整合进整体结构，不再进入 `/digest`，但仍可被下一次 `/construct` 读取。
