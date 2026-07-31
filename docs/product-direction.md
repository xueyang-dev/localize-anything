# Localize Anything 产品方向

状态：已定稿
生效日期：2026-07-30

本文是 Localize Anything 的产品定位与范围基准。架构、路线图、README、
Skill 和公开介绍都应与本文一致。仓库中已经存在但不再属于核心方向的能力，
应作为兼容实现、实验代码或历史快照说明，不应继续驱动产品扩张。

## 一句话定位

**Localize Anything 是面向 Coding Agent 的本地化专业能力层。**

英文短定位：

> **An agent-native localization workflow and review layer.**

Localize Anything 通过 Agent Skill 和轻量 QA 工具，为 Codex、Claude Code
等 Coding Agent 提供：

- 本地化前的范围分析；
- 产品概念、术语、风格和保留规则；
- 可复用的项目本地化记忆；
- 本地化后的独立质量审查；
- 少量、按风险排序的人工确认项。

目标不是替代 Coding Agent，而是让没有专业本地化经验的个人开发者和小型团队，
也能让 Agent 按专业流程完成多语言发布工作。

## 核心用户

核心用户是使用 Coding Agent 开发产品的：

- 个人开发者和独立开发者；
- 小型产品团队；
- 开源项目维护者。

这些用户通常已经可以让 Agent 完成 i18n 工程和翻译，但缺少完整流程、稳定术语、
范围判断、跨会话记忆和高效审查。

Localize Anything 暂不以大型企业本地化团队、语言服务供应商或专业翻译机构为
核心用户，也不与企业 TMS 竞争。

## 核心任务

典型请求是：

> 使用 Localize Anything，为这个项目增加俄语支持。

任务分为三个阶段。

### 本地化前

Localize Anything 指导 Agent 明确：

- 产品、用户和目标 locale；
- 本次覆盖的页面、组件、资源和动态边界；
- 哪些内容需要翻译、保留、locale formatting 或更多上下文；
- 核心产品概念、正式译法、禁止译法和风格；
- 可以复用的历史译文与人工决策；
- 本次任务的完成标准。

### 本地化执行

Coding Agent 负责：

- 建立或调整 i18n 架构；
- 抽取用户可见文案并创建目标语言资源；
- 实现语言切换、系统语言检测、持久化和 fallback；
- 修改代码并运行 build/test；
- 生成截图；
- 整理 Git diff、commit 或 PR。

Localize Anything 提供方法、上下文、约束和机械 QA，不重新实现 Coding Agent、
构建系统、测试系统或 Git。

### 本地化审查

初稿完成后，使用与生成阶段隔离的 review context 检查：

- 语义准确性和语言自然度；
- 术语、语气和产品概念一致性；
- 漏翻和错误翻译的保留内容；
- placeholder、markup、key 和结构；
- 页面或组件上下文；
- 需要用户决定的高风险歧义。

## 核心价值

### 完整的 Agent 本地化流程

避免逐页修补、无差别抽取、只跑 build、不建术语和不做语言审查。Agent 从一开始
就围绕范围、记忆、执行、独立 review 和发布证据工作。

### 稳定的项目本地化记忆

在 `.localize-anything/` 中保存并可通过 Git 共享：

- 产品概念和各 locale 的确认译法；
- 禁止译法和保留内容；
- 风格规则；
- 已审核 Translation Memory；
- 人工修订和历史问题。

更换 Agent、模型或会话后，产品语言仍应保持一致。

### 更低的人工 Review 成本

系统审查全部内容，自动放行低风险项，把用户需要亲自处理的内容压缩成少量高风险
决策。核心体验应类似：

> 326 条内容已经审查，只有 9 条需要你确认。

## 产品形态

### 主入口：Agent Skill

用户通过自然语言发起项目级任务。Skill 负责：

- 判断任务类型和深度；
- 建立范围和完成标准；
- 加载或初始化项目记忆；
- 生成并使用 Glossary、风格和保留规则；
- 指导 Coding Agent 执行工程工作；
- 启动独立 review；
- 汇总人工确认项和最终报告。

### 辅助能力：轻量 CLI

CLI 是 Agent 的确定性工具，不是主要用户界面。当前命令面保持精简：

```text
scan
glossary bootstrap
check
review
report
```

它适合扫描资源、比较 source/target、检查结构与覆盖、规范化 Glossary 和生成报告。
语义判断、代码修改、build/test、截图和 Git 工作由 Coding Agent 完成。

### 状态管理：Git

Git 负责 diff、history、rollback、branch、worktree、commit、PR 和团队 review。
Localize Anything 不建立一套平行的项目状态与审批系统。

### 不建设独立 Workbench

v1 使用 Agent 对话、Git diff 和最终 Review Report。旧 Workbench 与 Web UI 已在
Runtime 收敛中删除，不是兼容入口或路线图内容。

## 两种工作深度

### Standard

适合日常新增语言或更新文案：

1. 项目和范围预检；
2. 加载或生成 Glossary；
3. 创建风格和保留规则；
4. Coding Agent 完成本地化；
5. 确定性结构检查；
6. 独立 Agent Review；
7. 汇总高风险确认项；
8. 输出 Review Report。

### Release

适合正式发布。在 Standard 基础上增加：

- 主要页面目标语言截图；
- 页面级语义和视觉审查；
- build/test 结果确认；
- 语言切换、持久化、系统语言检测和 fallback 验证；
- clean Git diff；
- commit 或 PR；
- 将确认结果写回项目记忆。

不是所有任务都必须使用 Release。

## Review 模型

Review 同时覆盖三种粒度：

- 字符串层：source/target、placeholder、markup、数值、漏翻和禁止译法；
- 页面或组件层：实际语义、相邻文案、控件语气、跨页面一致性和截图结果；
- 产品概念层：同一概念跨项目和跨 locale 的一致表达。

底层可以使用 segment 和稳定 ID，但最终 Review 不能只审查孤立 segment。

## Glossary 与 Project Memory

Glossary 以产品概念为中心，而不是以单个语言对为中心。一个概念可以包含：

- 多个 source term；
- 各 locale 的 preferred / forbidden translation；
- `translate` 或 `preserve` 行为；
- 状态、范围、上下文和产品含义。

用户只维护一个 canonical Glossary。旧 `term-registry.csv`、
`term-decisions.jsonl`、term review 和 Knowledge Pack term 不再是运行时产品
概念；迁移读取器只把其中已确认的数据导入两个用户概念：

```text
Glossary
Project Memory
```

内部运行时可以保留可重建索引，但不应要求用户维护多套术语真相。

Translation Memory 是项目级复用能力，不是企业 TM Server。它用于复用已确认句子、
识别 source 变更、保留人工修订并减少重复翻译。

## 可翻译性分类

候选内容统一按以下类别判断：

```text
translate
preserve
locale_format
developer_only
dynamic_external
needs_context
```

覆盖完整的定义是：在本次声明的范围内，所有候选内容都已分类，并且所有
`translate` 内容都有目标语言结果。它不等于“项目中不存在任何源语言字符”。

## 质量输出

质量结果分为三层，不用单一分数替代：

- Deterministic checks：结构、key、placeholder、markup、明确术语约束、
  声明范围内覆盖和 preserve 完整性；
- Agent review：语义、自然度、语气、概念、上下文和文化表达；
- Human confirmation：产品正式译法、品牌、高风险歧义和 Agent 无法推断的决策。

## 完成标准

完成标准按项目类型动态生成。常见 Web App 的 Release 任务通常需要：

- 目标语言资源和声明范围内的可翻译内容已覆盖；
- 语言切换、持久化、系统语言检测和 fallback 可用；
- 明显漏翻已处理；
- 独立 Review 完成，高风险项已确认；
- 主要页面目标语言截图已生成；
- Coding Agent 已运行 build/test；
- Git diff 清晰，commit 或 PR 已准备。

## 成功指标

第一指标是 Review 成本下降：

- 总译文数量；
- Agent review 数量；
- 自动放行数量；
- 人工确认数量；
- 用户实际修改数量；
- Review 时间。

第二指标是本地化缺陷减少，包括漏翻、错译、术语不一致、误改保留内容、结构损坏
和风格偏差。

## v1 核心范围

v1 必须覆盖：

- Agent Skill；
- 项目 preflight、范围和完成标准；
- 可翻译性分类；
- 以产品概念为中心的 Glossary 和导入；
- 项目 Translation Memory 与风格指南；
- 独立 review context；
- 字符串、页面和概念三级 Review；
- 风险分级、低风险自动放行和人工确认汇总；
- Standard / Release；
- 最终 Review Report。

CLI 第一阶段优先支持 JSON、YAML、Android XML、Apple `.strings`、
`.xcstrings`、PO 和 XLIFF。其他格式可以先由 Coding Agent 直接处理。

## 退出核心的旧方向

以下能力不再属于产品核心：

- Provider 执行、consent、ledger 和 smoke evidence；
- 多 Agent 编排框架；
- Workflow 状态机、concurrency、idempotency 和 recovery 平台；
- Readiness Authorization Matrix、Claim Acceptance 和企业 signoff；
- Release claim audit 和 adapter promotion governance；
- 插件市场式权限与 trust；
- 大量用户可见协议 schema；
- Workbench Web UI；
- Document Evidence 和领导审批流程；
- Runtime 内产品化的 Benchmark Lab。

这些平台实现、公开命令和协议已经删除。历史架构只保留为文档快照和 Git 历史；
新工作不得以兼容为由恢复它们。

## 最终原则与承诺

- Agent 做理解、分类、翻译、审查、风险解释和代码修改；
- CLI 做扫描、对比、格式检查、覆盖统计、Glossary 规范化和报告；
- Git 做状态、历史、回滚和协作；
- 用户只处理真正需要人的产品含义、品牌、高风险译法和发布判断。

Localize Anything 不承诺自动生成绝对完美的专业翻译。它承诺：

> **让 Coding Agent 按专业本地化流程工作，稳定复用项目知识，系统审查所有译文，
> 并把开发者需要亲自处理的内容压缩到最少。**
