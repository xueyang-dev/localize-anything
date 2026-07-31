# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything 项目 Logo" width="220" />
</p>

<p align="center">
  <strong>面向 Coding Agent 的本地化专业能力层。</strong>
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

Localize Anything 帮助 Coding Agent 在真实项目中完成一条清晰、可审查的本地化链路：

```text
scan
→ glossary bootstrap
→ Coding Agent 本地化
→ 项目原生 build/test
→ check
→ independent review
→ human confirmation
→ report
```

它不替代 Coding Agent、项目构建系统、Git 或人工产品判断。它负责范围、Project
Memory、Glossary、确定性检查、独立审查和少量高风险确认。

## 当前实现

仓库当前只有一个公开 CLI：`localize`。默认路径只包含五个命令：

```bash
localize scan
localize glossary bootstrap
localize check
localize review
localize report
```

旧的 `localize-anything` 平台 CLI、Provider、Workbench、readiness、workflow、
signoff、Knowledge Pack、generation/delivery orchestration 和对应协议已移除。
格式缺口由 Coding Agent 使用项目原生工具处理，不会自动退回旧平台。

当前核心提供：

- 可提交到 Git 的 Project Memory；
- 以产品概念为中心的单一 `glossary.json`；
- 已确认旧术语、TM、style 和 decisions 的保守导入；
- JSON、YAML/TOML、Android XML、Apple `.strings` / `.xcstrings`、PO/POT 和
  XLIFF 的扫描与结构检查；
- placeholder、key、markup、Android escape/CDATA 和 locked Glossary 检查；
- 面向新 Agent context 的独立 review packet；
- finding 关联的人工确认门；
- 精简的 JSON/Markdown 报告。

Markdown/HTML、CSV/TSV/XLSX、Word OpenXML、字幕和 Wesnoth handler 作为有限的
Python 兼容能力保留，但不是默认 CLI 回退路径。

## 安装

需要 Python 3.11+：

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
```

## 使用

先扫描项目。未声明 source 时，`scan` 只列出可识别资源：

```bash
localize scan /path/to/project
```

声明一次本地化任务：

```bash
localize scan /path/to/project \
  --source-locale en \
  --target-locale ru \
  --source locales/en.json
```

然后建立 canonical Glossary：

```bash
localize glossary bootstrap /path/to/project
```

Coding Agent 接下来修改应用代码和目标语言资源，并运行项目自己的验证，例如：

```bash
npm test
npm run build
git diff
```

Localize Anything 不包装或替代这些命令。完成工程修改后运行：

```bash
localize check /path/to/project \
  --target locales/ru.json

localize review /path/to/project \
  --target locales/ru.json
```

把 `.localize-anything/review-packet.json` 交给未参与生成译文的新 Agent context。
审查结果格式为：

```json
{
  "reviewer": "independent-agent",
  "findings": [
    {
      "id": "navigation.share",
      "severity": "high",
      "status": "needs_human_confirmation",
      "note": "产品动作含义需要确认"
    }
  ]
}
```

导入审查并生成报告：

```bash
localize review /path/to/project \
  --target locales/ru.json \
  --findings review.json

localize report /path/to/project
```

只有 `needs_human_confirmation` 的开放 finding 可以接受人工确认：

```bash
localize report /path/to/project --confirm confirmations.json
```

确认文件示例：

```json
{
  "confirmations": [
    {
      "finding_id": "navigation.share",
      "decision": "使用“Поделиться”",
      "note": "产品所有者确认"
    }
  ]
}
```

所有核心状态位于项目的 `.localize-anything/` 目录。

## 职责边界

| 角色 | 职责 |
| --- | --- |
| Localize Anything Skill | 范围、Glossary、Project Memory、流程、独立 Review、风险汇总 |
| `localize` CLI | 扫描、结构检查、review packet、finding/confirmation 约束、报告 |
| Coding Agent | i18n 架构、代码和资源修改、语言切换、fallback、build/test、截图、Git |
| 用户 | 产品含义、品牌、正式术语、高风险歧义和发布判断 |

确定性检查不证明译文自然或语义正确；独立 Agent Review 也不等同于人工发布批准。
`ready` 只表示当前声明范围内的核心检查、Review 和确认已完成，不替代项目原生
build/test、截图或 Git Review。

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

- [产品方向](docs/product-direction.md)
- [当前架构](docs/architecture.md)
- [架构路线图](docs/architecture-roadmap.md)
- [格式处理边界](docs/adapters.md)
- [核心数据契约](protocol/SPEC.md)
- [Agent Skill](skills/localize-anything/SKILL.md)
- [Phase 2 真实项目验证](docs/validation/phase2-live-dry-run.md)

历史 v0.4 平台设计只保留在
[Legacy Architecture Snapshot](docs/architecture-v0.4-legacy.md) 和 Git 历史中。

## 非目标

Localize Anything 不是：

- 翻译模型或 Provider 平台；
- 企业 TMS；
- 通用多 Agent orchestration framework；
- Workbench 或发布治理系统；
- Git、CI 或项目构建系统的替代品；
- “零源语言字符”或专业翻译质量的自动认证。

## License

MIT
