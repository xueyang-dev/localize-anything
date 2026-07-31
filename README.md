# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything 项目 Logo" width="220" />
</p>

<p align="center">
  <strong>面向 Coding Agent 的本地化专业能力层。</strong><br />
  <sub>An agent-native localization workflow and review layer.</sub>
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

你已经让 Coding Agent 帮你写代码了。现在让它为项目增加俄语支持——它能翻，但翻完之后呢？术语是否一致、关键概念有没有译对、几百条译文怎么审查——这些问题 Agent 单靠自己解决不了。

**Localize Anything 给它一套专业本地化流程：** 扫描范围、建立项目术语表、系统审查所有译文、把需要你亲自确认的高风险项压缩到个位数。它不是一个翻译工具，也不是又一个 CI 平台——它是嵌入 Agent 工作流的本地化专业层，让项目记忆跨会话复用，让审查从「逐条看」变成「只看那几条真正需要你决定的」。

## 工作流

```text
localize scan
→ localize glossary bootstrap
→ Coding Agent 本地化（项目原生 build/test）
→ localize check
→ localize review
→ 人工确认
→ localize report
```

Localize Anything 不替代 Coding Agent、项目构建系统、Git 或人工产品判断。它负责范围、Project Memory、Glossary、确定性检查、独立审查和少量高风险确认。

## 快速上手

需要 Python 3.11+：

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
```

对目标项目声明一次本地化任务，建立 Project Memory：

```bash
localize scan /path/to/project \
  --source-locale en \
  --target-locale ru \
  --source locales/en.json
```

生成 canonical Glossary：

```bash
localize glossary bootstrap /path/to/project
```

接下来 Coding Agent 修改应用代码与目标语言资源，并运行项目自己的验证（`npm test`、`npm run build`、`git diff` 等）。工程修改完成后：

```bash
localize check /path/to/project --target locales/ru.json
localize review /path/to/project --target locales/ru.json
```

把 `.localize-anything/review-packet.json` 交给一个未参与生成译文的独立 Agent context 审查，导入审查结果并生成报告：

```bash
localize review /path/to/project --target locales/ru.json --findings review.json
localize report /path/to/project
```

只有状态为 `needs_human_confirmation` 的开放 finding 可以接受人工确认：

```bash
localize report /path/to/project --confirm confirmations.json
```

所有核心状态保存在目标项目的 `.localize-anything/` 目录，可随 Git 提交与共享。

## 让 Coding Agent 使用

主入口是 Agent Skill，CLI 是它的确定性工具。

- **Codex**：把仓库的 `skills/localize-anything/` 目录作为可用 Skill（或复制到你的 Codex skills 目录），然后直接提出：
  > 使用 Localize Anything，为这个项目增加俄语支持。
- **Claude Code**：把同一目录放入项目的 `.claude/skills/localize-anything/`（保留 `SKILL.md` 和 `references/`），使用同样的自然语言请求即可。

Skill 只指导流程；代码修改、资源编辑、build/test 和 Git 操作仍由 Coding Agent 使用项目原生命令完成。

## 两种工作深度

| 深度 | 适用场景 | 内容 |
| --- | --- | --- |
| **Standard** | 日常新增语言、更新文案 | 范围、Glossary、Agent 实施、确定性检查、独立 Review、高风险确认 |
| **Release** | 正式发布 | Standard 全部内容 + 页面截图、页面级 Review、项目原生 build/test、locale 切换/持久化/检测/fallback 验证、干净 Git diff、发布证据 |

## 职责边界

| 角色 | 职责 |
| --- | --- |
| Localize Anything Skill | 范围、Glossary、Project Memory、流程、独立 Review、风险汇总 |
| `localize` CLI | 扫描、结构检查、review packet、finding/confirmation 约束、报告 |
| Coding Agent | i18n 架构、代码和资源修改、语言切换、fallback、build/test、截图、Git |
| 用户 | 产品含义、品牌、正式术语、高风险歧义和发布判断 |

确定性检查不证明译文自然或语义正确，独立 Agent Review 也不等于人工发布批准。`ready` 只表示当前声明范围内的核心检查、Review 和确认已完成，不替代项目原生 build/test、截图或 Git Review。

## 开发验证

```bash
python -m unittest discover -s tests -p 'test_*.py'
python -m compileall -q runtime tests
```

协议和 adapter manifest 使用仓库内的 dependency-free validator：

```python
from pathlib import Path
from runtime.localize_anything.contracts import validate_adapter_tree
from runtime.localize_anything.schema_validation import validate_protocol_tree

assert validate_protocol_tree(Path("protocol"))["status"] == "pass"
assert validate_adapter_tree(Path("adapters"))["status"] == "pass"
```

## 文档

- [产品方向](docs/product-direction.md) — 定位与范围基准，一切文档的源头
- [当前架构](docs/architecture.md)
- [架构路线图](docs/architecture-roadmap.md)
- [格式处理边界](docs/adapters.md) — 核心格式与受限兼容方向的完整说明
- [核心数据契约](protocol/SPEC.md)
- [Agent Skill](skills/localize-anything/SKILL.md)
- [迁移说明](docs/migration/agent-native-core-migration.md) — 从旧平台迁移到五命令核心
- [0.5.0 发布说明](docs/releases/0.5.0-release-notes.md)

历史 v0.4 平台设计仅保留在 [Legacy Architecture Snapshot](docs/architecture-v0.4-legacy.md) 与 Git 历史中。

## 非目标

Localize Anything 不是：

- 翻译模型或 Provider 平台；
- 企业 TMS；
- 通用多 Agent orchestration framework；
- Workbench 或发布治理系统；
- Git、CI 或项目构建系统的替代品；
- 「零源语言字符」或专业翻译质量的自动认证。

## License

MIT
