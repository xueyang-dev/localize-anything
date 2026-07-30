# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything 项目 Logo" width="220" />
</p>

<p align="center">
  <strong>面向 Coding Agent 的本地化专业能力层。</strong>
</p>

<p align="center">
  目标：让 Agent 按专业流程完成本地化，复用项目语言知识，审查全部译文，只把少量高风险决策交给你。
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

<p align="center">
  <img alt="许可证：MIT" src="https://img.shields.io/badge/license-MIT-blue" />
  <img alt="持续集成状态" src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" />
  <img alt="当前发布：v0.4.1" src="https://img.shields.io/badge/release-v0.4.1-blue" />
  <img alt="主入口：Agent Skill" src="https://img.shields.io/badge/interface-Agent%20Skill-blueviolet" />
</p>

---

当前仓库已经提供 Agent Skill、结构 QA、Translation Memory 和多种资源格式处理
能力。新的 Skill 开始要求 Codex、Claude Code 等 Coding Agent 在本地化前明确
范围和语言约束，并在完成初稿后使用独立 context 复查。以产品概念为中心的
canonical Glossary、统一 Project Memory、页面级 Review 和自动风险压缩仍在按
目标 v1 整合。

Coding Agent 已经能修改代码、建立 i18n、运行 build/test、生成截图和准备 PR。
Localize Anything 不重复实现这些能力；它补上的是专业本地化流程和低成本 Review。

> **An agent-native localization workflow and review layer.**

## 适合谁

核心用户是使用 Coding Agent 开发产品的：

- 个人开发者和独立开发者；
- 小型产品团队；
- 开源项目维护者。

典型请求：

> 使用 Localize Anything，为这个项目增加俄语支持。

它暂不以大型企业本地化团队、语言服务供应商或专业翻译机构为核心用户，也不与
企业 TMS 竞争。

## 它解决什么问题

### 让 Agent 使用完整流程

普通 Agent 容易逐页修补、无差别抽取字符串、只运行 build、忽略术语和语言审查。
目标工作流要求任务从范围、项目记忆和完成标准开始，并以独立 Review 和风险汇总
结束。当前 Skill 已纳入这些流程要求，配套的精简 CLI 与统一报告仍在迁移。

### 保留稳定的项目语言

目标 v1 的 Project Memory 将在 `.localize-anything/` 中保存并可通过 Git 共享：

- 产品概念和各语言的确认译法；
- 禁止译法与保留内容；
- 风格规则；
- 已审核 Translation Memory；
- 人工修订和历史问题。

当前运行时已经保存配置、Translation Memory 和多种术语/审核产物；将它们合并为
单一 Project Memory 和概念级 Glossary 仍是 migration direction。完成后，即使
更换 Agent、模型或会话，确认过的产品语言也应保持一致。

### 降低人工 Review 成本

目标体验是让 Agent 审查全部内容、按可见理由放行低风险项，并把产品正式译法、
品牌和高风险歧义整理成少量人工确认项。当前 Skill 已要求独立 Review 和风险路由；
自动放行、统计和完整报告仍在整合。理想结果是：

```text
Translated items: 412
Agent-reviewed: 412
Auto-cleared: 397
Human confirmation required: 15
Human-edited after review: 6
```

## 目标职责边界

| 角色 | 职责 |
| --- | --- |
| Localize Anything Skill | 范围、Glossary、风格、项目记忆、流程、独立 Review 和最终报告 |
| Coding Agent | i18n 架构、代码修改、语言资源、build/test、截图、Git diff、commit 和 PR |
| 轻量 CLI | 扫描、source/target 对比、placeholder/markup/key 检查、覆盖统计和报告数据 |
| Git | diff、history、rollback、branch、worktree、commit、PR 和团队 Review |
| 用户 | 产品含义、品牌、高风险译法和最终发布判断 |

## Skill 工作深度与目标 v1 工作流

当前 Skill 已定义 Standard 和 Release 两种工作深度。它们是 Agent 工作方法，不是
v0.4.1 运行时已经完整实现的两个产品模式；配套命令、统一 Project Memory、页面
Review 和自动报告仍在整合。

### Standard

适合日常新增语言或更新文案：

```text
项目与范围预检
-> Glossary、风格与保留规则
-> Coding Agent 完成本地化
-> 确定性结构检查
-> 独立 Agent Review
-> 高风险人工确认
-> Review Report
```

### Release

适合正式发布。在 Standard 基础上增加：

- 主要页面目标语言截图；
- 页面级语义和视觉审查；
- build/test 结果确认；
- 语言切换、持久化、系统语言检测和 fallback 验证；
- clean Git diff；
- commit 或 PR；
- 将确认结果写回项目记忆。

不是所有任务都需要 Release。

## 目标 Review 模型

目标 v1 不只审查孤立字符串：

1. **字符串层**：source/target、placeholder、markup、数值、漏翻和禁止译法；
2. **页面或组件层**：实际语义、相邻文案、控件语气、跨页面一致性和截图结果；
3. **产品概念层**：同一概念在整个产品和不同目标语言中的一致表达。

当前运行时已有字符串级结构 QA；页面/组件和产品概念级 Review 已写入 Skill
方法，但还没有作为独立自动化引擎完整交付。目标质量输出保持三层分离：

- Deterministic checks；
- Agent review；
- Human confirmation。

不使用一个模糊总分替代它们。

## Glossary 与 Project Memory

目标 canonical Glossary 以产品概念为中心，而不是以单个语言对为中心。一个概念
可以包含多个 source term、各 locale 的首选/禁止译法、保留行为、范围、状态和
上下文。

用户只需要理解两个长期概念：

```text
Glossary
Project Memory
```

当前运行时中分散的 term registry、term decisions、review queue 和 Knowledge
Pack term 将逐步合并到这两个概念，而不是继续增加用户需要维护的文件。

Translation Memory 是项目级能力，不是企业 TM Server。它用于复用已确认句子、
识别 source 变化、保留人工修订并减少重复翻译。

## 可翻译性与覆盖

候选内容不只分成“已翻译/未翻译”，而是：

```text
translate
preserve
locale_format
developer_only
dynamic_external
needs_context
```

覆盖完整表示：本次声明范围内的候选内容都已分类，所有 `translate` 内容都有目标
语言结果。它不表示项目里不能出现任何源语言字符。

## 当前状态

**当前公开版本：**
[v0.4.1 — Workbench UI Wiring](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.4.1)

2026-07-30，项目完成产品方向重置：Agent Skill 成为主入口，轻量 CLI 只做机械
检查，Git 负责状态管理，独立 Review 和人工成本下降成为核心体验。

仓库仍包含 v0.4.1 的广义参考运行时，包括 Workbench、Provider evidence、
workflow orchestration、authorization、release audit 和大量 protocol artifacts。
这些代码暂时保留用于兼容和提取可复用能力，但不再定义产品方向，也不再是核心
路线图。

目标 v1 的精简命令面、canonical Glossary 和 Project Memory 正在从现有能力中
整合。README 不把尚未完成的迁移描述成已发布功能。

## 如何使用

### 通过 Coding Agent

当 Agent 已加载 Localize Anything Skill 时，直接描述项目级任务：

```text
使用 Localize Anything，为这个项目增加中文和俄语支持。
使用 Release 深度，完成主要页面截图、build/test 和 PR 准备。
```

当前 Skill 会指导 Agent 做范围和现有记忆预检、修改项目、运行可用的机械检查，
并在独立 context 中 Review。canonical Glossary、自动低风险放行和统一风险报告
仍按目标 v1 逐步接入。

Skill 源文件位于
[skills/localize-anything/SKILL.md](skills/localize-anything/SKILL.md)。

### 当前 CLI 开发预览

需要 Python 3.11+：

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
```

当前运行时可以只读检查真实项目：

```bash
localize-anything inspect /path/to/project
```

目标 v1 将把 Agent 常用机械能力收敛为 `scan`、`glossary bootstrap`、`check`、
`review` 和 `report` 等小型能力组；这些名称是方向，不代表当前版本已经全部提供。

## 当前可复用的确定性能力

仓库已经包含可用于精简 v1 的实现：

- segment 和稳定 ID；
- candidate term extraction、禁止译法和 term review；
- exact/fuzzy Translation Memory；
- working context 构造；
- placeholder、markup、key、escape 和资源结构 QA；
- source/target coverage；
- staging 与 Git diff 配合；
- JSON、YAML/TOML、Android XML、Apple `.strings`、`.xcstrings`、PO/POT、
  XLIFF、字幕、表格、Markup 和 Word OpenXML 等现有处理代码。

具体格式边界见 [适配器说明](docs/adapters.md)。历史基准和发布证据仍可用于验证
这些实现，但不再主导产品定位。

## 它不是什么

Localize Anything 不是：

- 独立翻译模型；
- 模型 Provider 管理平台；
- 多 Agent 编排框架；
- 企业 TMS、审批或权限系统；
- Git、CI/CD 或项目构建系统的替代品；
- 通用开发 Workbench；
- 独立 i18n 框架生成器；
- 全自动专业质量认证系统；
- “绝对完美翻译”或“零源语言字符”的承诺。

它可以要求 Coding Agent 完成 build/test、截图和 PR，但不重新实现这些系统。

## 产品文档

- [产品方向](docs/product-direction.md)
- [目标架构](docs/architecture.md)
- [路线图](docs/architecture-roadmap.md)
- [公开声明边界](docs/public-claim-reconciliation.md)
- [ADR 0002：Coding Agent 本地化工作流与审查层](docs/decisions/0002-coding-agent-localization-layer.md)
- [v0.4 旧架构快照](docs/architecture-v0.4-legacy.md)
- [变更记录](CHANGELOG.md)

## 仓库结构

```text
skills/            Agent Skill：产品主入口
runtime/           当前 Python 参考运行时与迁移来源
adapters/          现有格式处理清单
protocol/          v0.4 兼容协议，不再是产品定位来源
benchmarks/        历史与回归验证
tests/             单元测试和集成测试
docs/              产品方向、架构、边界和实现文档
```

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
