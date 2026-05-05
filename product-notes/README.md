# Product Notes

本目录用于整理 scaudit 的产品资料。当前阶段仍然只整理设计和文案，不编写程序代码。

## 当前判断

scaudit 的产品方向成立，但最合理的定位不是“新的 annotation model”，而是：

```text
single-cell annotation audit and reporting framework
```

它的用户价值来自把原本分散在 notebook、marker 表、reference mapping、模型输出、人工判断和图表里的 annotation 过程，整理成可审计、可复现、可解释、可交付的结果。

## 推荐阅读顺序

1. [Product Strategy Review](./product-strategy-review.md): 产品定位、目标用户、市场需求、差异化、风险与是否值得做。
2. [MVP Scope and Development Gate](./mvp-scope.md): 第一版该做什么、不做什么，以及开发前必须锁定的设计 contract。
3. [Product Roadmap](./roadmap.md): 从 zero 到 MVP、成熟科学工具、industry-level product 的阶段路线图。
4. [Development Contracts](./contracts.md): Evidence schema、gene harmonization、reference scoring、ensemble decision、LLM boundary 的正式 contract。
5. [HTML Report Architecture](./report-architecture.md): 多页面 HTML/Quarto 报告的信息架构、导航、页面层级、图表与 MVP 报告范围。
6. [User Workflow and CLI Flow](./user-workflow.md): 使用者从 input data 到 draft report、review、final annotation 的步骤和指令设计。
7. [Configuration File Design](./configuration.md): `config.toml` 配置文件结构、validate/plan/run 流程、CLI override 与 resolved config 策略。
8. [Reference Management Workflow](./reference-management.md): reference search/recommend/download/add/use/list/update、local registry 与 config 自动更新设计。
9. [CLI UX and Terminal Output](./cli-ux.md): rich terminal UI、颜色、spinner、progress bar、表格、错误提示和最终摘要的 CLI 体验标准。
10. [Product Design](./product-design.md): CLI、evidence、reference、LLM、Quarto report、human review 与输出系统的完整设计。
11. [Critical Gaps and Design Blind Spots](./critical-gaps.md): coding 前必须补齐的关键缺口。
12. [Tooling and Dependency Strategy](./tooling-dependencies.md): 工具矩阵、Pixi feature 设计 与 MVP dependency 策略。

## 核心文档

- [Project Description](./project-description.md): 精简后的正式项目描述与产品承诺。
- [Product Roadmap](./roadmap.md): 从零开始到 MVP、成熟产品和产业级平台的完整路线图。
- [Development Contracts](./contracts.md): 开发前必须锁定的五个核心 contract。
- [HTML Report Architecture](./report-architecture.md): 高级、清晰、可导航的 HTML 报告结构设计。
- [User Workflow and CLI Flow](./user-workflow.md): CLI 使用流程、分阶段运行、review/import/finalize 的决策模型。
- [Configuration File Design](./configuration.md): 手动填写 `config.toml` 并一次执行的配置文件方案。
- [Reference Management Workflow](./reference-management.md): public/custom reference 的下载、注册、选择、更新和写回 config 策略。
- [CLI UX and Terminal Output](./cli-ux.md): 高级 CLI 输出体验标准。
- [Product Vision](./vision.md): 产品用途、意象、存在目的、核心表达。
- [Design Philosophy](./design-philosophy.md): annotation 决策过程、透明性、不确定性、人机协作、LLM 角色与可复现性原则。
- [Methods](./methods.md): 可用于论文或技术白皮书的 Methods 章节，包含数学定义、pipeline formalization 与 annotation record 草案。
- [Academic Framing](./academic-framing.md): 论文风格的项目描述、literature framing、conceptual framework、方法层与 citation placeholders。
- [Branding](./branding.md): logo 方向、视觉含义、tagline、颜色方向、使用场景与后续需要准备的 asset 版本。

## 开发前必须锁定

进入 coding 前，至少需要明确：

```text
1. Evidence schema
2. Gene ID harmonization policy
3. Reference metadata and scoring schema
4. Ensemble decision rule
5. LLM input/output contract and forbidden behavior
```

这些内容决定第一版实现是否稳健。若未锁定，容易写出功能很多但判断逻辑不可靠的工具。

## 当前状态

资料已从“想法收集”收敛为“产品定位 + MVP 范围 + 开发 contract”。下一步建议审阅并确认 [Development Contracts](./contracts.md)，再开始实现第一个 vertical slice。
