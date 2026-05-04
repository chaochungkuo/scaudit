# Product Vision

## Vision Statement

scaudit aims to redefine single-cell annotation as a **transparent and explainable process**, bridging computational models and biological interpretation.

```text
Not just annotation — but annotation you can trust.
```

## 用途

这个项目不是单纯用于：

```text
predict cell types
```

而是用于：

```text
analyze, validate, and explain cell type annotation
```

更精确地说，给定一个 single-cell dataset，这个工具应该能够：

- 选择合适的 reference。
- 整合多种 annotation 方法，包括 marker、reference、model。
- 产生可解释的 evidence。
- 告诉使用者哪些结果可靠、哪些结果不可靠。

核心输出不是一个单一 label，而是：

```text
一个完整的 annotation report + decision trace
```

## 产品意象

这个工具应该像：

```text
一个严谨的生物资讯专家，在旁边帮使用者审核每一个 annotation
```

而不是：

```text
一个黑箱 AI 告诉使用者答案
```

### 目标体验

现有工具常见输出类似：

```text
Cluster 5 = macrophage
```

本项目期望输出类似：

```text
Cluster 5

Conclusion:
Macrophage

Why:
- Marker genes (LYZ, C1QA, CD68) strongly support myeloid lineage
- Reference mapping (Mouse Heart Atlas) shows high similarity
- scANVI prediction agrees

What is uncertain:
- Subtype (alveolar vs inflammatory) not resolved

What to check:
- MARCO, APOE, CCR2

Confidence:
High at lineage level, medium at subtype level
```

产品感觉应接近：

```text
lab meeting discussion + reviewer + annotation expert
```

## 存在目的

这个工具存在的真正目的不是：

```text
让 annotation 更快
```

而是：

```text
让 annotation 更可靠、更透明、更可被信任
```

## 当前问题

目前 single-cell annotation 存在的问题：

- 太依赖 reference，但 reference 不完美。
- 太依赖模型，但模型常常是黑箱。
- 缺乏标准化解释。
- 很难知道哪里可能是错的。

## 要解决的问题

本项目要解决的问题：

- 把 annotation 从“结果”变成“过程”。
- 把 black box 变成 audit trail。
- 把 confidence 变成可解释的 evidence。
- 帮使用者发现：
  - ambiguous clusters
  - novel states
  - incorrect assumptions

## README 一句话版本

```text
A transparent, evidence-based single-cell annotation framework
that explains, validates, and challenges cell type assignments
using multi-reference data, computational models, and LLM-assisted reasoning.
```

## 产品 Slogan 候选

```text
Not just annotation — but annotation you can trust.
```

```text
From labels to evidence.
```

```text
Explain your cells.
```

## 最核心问题

这个工具不是在回答：

```text
这是什么细胞？
```

而是在回答：

```text
为什么这是这个细胞？我应该相信吗？
```

## 设计哲学

这份内容应作为 project description / design philosophy 使用，帮助后续开发避免把项目做成“又一个 annotation tool”。

更正式的英文项目描述见 [Project Description](./project-description.md)，设计原则见 [Design Philosophy](./design-philosophy.md)。
