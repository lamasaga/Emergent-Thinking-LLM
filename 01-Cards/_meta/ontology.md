---
id: "ontology"
title: "知识库元结构"
type: "meta"
created: "2026-07-07"
updated: "2026-07-07"
status: "active"
---

# 知识库元结构

> 本文件是当前知识结构的「活契约」。AI 在每次 `/construct`、`/digest`、`/analyze` 前都应读取它。

## 当前领域（顶层骨架）

> 由 `/construct` 基于种子内容生成。初始为空，等待建构。

## 允许的卡片类型

- `domain`：领域卡片，骨架。
- `concept`：抽象概念。
- `entity`：具体的人、机构、作品、理论。
- `model`：思维模型、解释框架。
- `method`：方法、技巧、流程。
- `conflict`：冲突与张力的记录。
- `note`：暂时无法归类的想法。

## 目录组织原则

- 领域卡片统一放在 `01-Cards/domains/`。
- 实例卡片按 `/construct` 或 `/digest` 决定的子目录存放。
- 子目录命名使用 `kebab-case`，与内容主题一致。

## 允许的 relation 类型

- `belongs-to`：属于某个领域或概念。
- `extends`：扩展、深化某个概念。
- `conflicts-with`：与某个概念冲突。
- `supports`：支持某个概念或立场。
- `example-of`：某个概念的具体例子。
- `applies-to`：应用于某个场景或问题。
- `influences`：影响某个概念或领域。

## 命名约定

- `id`：`kebab-case`，全局唯一。
- 文件名：与 `id` 一致，例如 `cognitive-scaffolding.md`。
- 中文标题放在 `title` 字段和 `# 标题` 中。
- 标签：`kebab-case` 或中文，小写。

## 实例引用上限

- `01-Cards/` 卡片：原始资料实例 ≤ 4 条。
- `02-Profile/` 档案：原文摘录 ≤ 10 条。
