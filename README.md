# Localize Anything

<p align="center">
  <img src="docs/assets/logo-localize-anything-transparent.png" alt="Localize Anything 项目 Logo" width="220" />
</p>

<p align="center">
  面向真实代码库的智能体本地化交付框架。
</p>

<p align="center">
  大模型可以生成译文；Localize Anything 负责把译文变成可验证、可审查、可回滚的交付结果。
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

<p align="center">
  <img alt="许可证：MIT" src="https://img.shields.io/badge/license-MIT-blue" />
  <img alt="持续集成状态" src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" />
  <img alt="当前版本：v0.4.1" src="https://img.shields.io/badge/release-v0.4.1-blue" />
  <img alt="质量检查：确定性规则" src="https://img.shields.io/badge/QA-deterministic-green" />
  <img alt="应用策略：先暂存，后写入" src="https://img.shields.io/badge/apply-staged%20first-blueviolet" />
</p>

---

Localize Anything 面向需要在真实代码库中开展本地化工作的开发者和本地化团队。它不是简单的翻译脚本，也不是把模型输出直接写回项目的工具；它提供一套可追踪、可审查、可复现的交付流程：提取可翻译内容，生成目标语言草稿，使用确定性规则检查结构，将结果写入暂存目录，并在人工检查应用计划和确认运行 ID 后再写入源码项目。

## 适合使用的场景

当你需要处理以下任务时，可以使用 Localize Anything：

- 本地化真实代码库，而不是翻译零散字符串；
- 保护占位符、XML/HTML 标记、资源键、转义符和文件结构；
- 为 Word 文档、Android、iOS 或常见文本资源生成可审查的目标语言文件；
- 在写入源码前先查看暂存文件、QA 证据、交付决策和应用计划；
- 维护已有译文时保留未变化的已审核内容，避免无意义重翻；
- 在盲测、全新本地化、维护和重写场景之间使用不同的参考译文策略。

## 当前状态

**当前公开版本：** [v0.4.1 — Workbench UI Wiring](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.4.1)

v0.4.1 优化 Workbench WebUI：移除仿 macOS 窗口控制装饰，将本地化模式选择连接到 agent 的 `operating_mode` 和 `reference_policy`，新增基于 `/api/sessions` 的会话面板，并在项目路径、目标语言和响应目录缺失时先给出内联校验错误。

v0.4.0 新增的 Word OpenXML 文档本地化和显式 opt-in Android merged dependency resource overlay 仍是当前功能基线。旧二进制 `.doc`、图片文字、嵌入对象内容和 provider-backed translation 语义质量仍不属于确定性覆盖声明。

截至 PR #57，仓库已实现一组架构 seed，把源项目、用户审核知识、外部模型/provider 结果证据、确定性 QA、范围化人工审核和可追踪交付串联起来。这些是已实现的架构 seed，不是新增的 v0.4.1 稳定发布声明。Localize Anything 不承诺“一键完美翻译”或未经合格审核的生产质量；输出保持暂存，真正 apply 仍需要显式审阅和确认。

已验证的工程结果包括：

- v0.4.1 Workbench UI 状态、模式透传、会话端点和前端校验验证通过；
- v0.4.0 Word adapter 提取、重建、校验覆盖通过；
- Word `.docm` 宏字节保留验证通过；
- Workbench 文件/文件夹导入 API 和 UI 冒烟测试通过；
- 显式 opt-in 的 Android merged dependency resource overlay 测试通过；
- v0.3.2 Android coverage diagnostics 验证通过；
- v0.3.1 发布审计通过；
- 运行时代码已确认不包含已检查的私有本地路径模式；
- 单元测试、协议验证、适配器契约验证、编译检查和公开回归脚本通过；
- AntennaPod 一次性克隆项目的只读检查和冒烟测试通过，未修改已跟踪源文件；
- Android 真实项目压力矩阵记录了 AntennaPod、NewPipe、Tusky 和 Fossify File Manager 的检查/合成流程证据；
- v0.2.3 Android 资源可靠性回归检查通过；
- v0.2.1 运行模式基准检查通过；
- AntennaPod DeepSeek 实测覆盖日语、韩语两个目标语言，每种语言 869 个文本段，确定性 QA 未发现阻断问题或警告，两个语言版本均编译成功。

这些结果证明的是流程、结构保护和交付证据的正确性，不等同于人工译文质量评价，也不表示生成结果可以免审查直接上线。详细记录见 [变更记录](CHANGELOG.md)、[适配器契约](docs/adapters.md)、[Android 覆盖范围模型](docs/android-coverage-model.md)、[v0.3.1 发布审计](docs/v0.3.1-release-audit.md) 和 [真实 Android 项目压力矩阵](docs/android-real-project-stress-matrix.md)。

## 为什么需要它

大模型可以生成读起来合理的文本，但真正的软件本地化交付还要解决更具体的工程问题：

- 占位符、标记、转义符和资源键不能被破坏；
- 已经审核过的译文不应该被无意义重写；
- 参考译文在盲测和维护场景下需要不同的可见性策略；
- 每次运行都应该留下可复查的清单、QA 结果、审核状态和应用计划；
- 工具不能在没有确认的情况下覆盖、删除或污染源码项目。

Localize Anything 提供的是代码库、智能体或人工译者与最终交付物之间的工程层。运行时负责结构检查、暂存、冲突检测、打包和应用计划；智能体与模型服务负责语义生成；人工审核负责最终判断。

## 工作流程

**提取 → 生成 → 校验 → 暂存 → 审核 → 应用**

1. 从真实项目支持的资源格式中提取可翻译内容。
2. 根据运行模式决定哪些内容需要生成、哪些内容必须保留。
3. 通过宿主智能体、模型服务或人工流程生成目标语言草稿。
4. 使用程序检查占位符、标记、转义符、资源键和文件结构。
5. 在代码库之外暂存输出，供人工检查。
6. 打包清单、QA 证据、审核状态、交付决策和应用计划。
7. 只有在明确确认运行 ID 后才应用变更，并在替换文件前创建备份。

![Localize Anything 工作流：从项目智能体到备份后应用的九个步骤](docs/assets/workflow-dark.svg)

## 核心保证

| 保证 | 实现方式 |
| --- | --- |
| 先暂存，后写入 | 生成文件写入隔离的暂存目录，不直接修改源码项目。 |
| 确定性 QA | 使用程序检查占位符一致性、标记完整性、转义符、资源键和格式规则。 |
| 不静默覆盖 | 出现冲突时阻止应用，直到问题得到处理。 |
| 确认后应用 | 必须提供匹配的 `--confirm-run-id`；替换文件前会创建备份。 |
| 源文件变更检测 | 使用 SHA-256 检测运行期间出现的意外修改。 |
| 维护模式保留 | 在经过验证的维护流程中，保留未发生变化的已审核译文，以及仅存在于 Android 目标语言文件中的资源。 |
| 参考译文隔离 | 盲测模式不会让已有译文进入生成环节所使用的文件。 |
| 交付过程可审查 | 清单、QA 结果、审核确认范围和文件操作均可检查。 |

完整安全设计见 [安全说明](docs/security.md)。

## 快速开始

### 从源码安装

需要使用 Python 3.11+。

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
```

Windows PowerShell 可使用：

```powershell
.venv\Scripts\Activate.ps1
```

### 运行回归基准

```bash
python benchmarks/v022-android-resource-reliability/run.py
python benchmarks/v022-android-resource-reliability/source_sets.py
python benchmarks/v022-android-resource-reliability/risk_classification.py
python benchmarks/v021-mode-system/run.py
```

### 检查真实项目

```bash
localize-anything inspect /path/to/project
```

## 示例工作流

下面的命令使用合成草稿，为 Android 源语言文件创建一份日语全新本地化的暂存交付包。整个过程不会调用外部模型，也不会直接写入项目。

```bash
localize-anything localize-run /path/to/project \
  --source-locale en-US \
  --target-locale ja \
  --source-file app/src/main/res/values/strings.xml \
  --operating-mode greenfield_localization \
  --reference-policy style_only \
  --run-id greenfield-001 \
  --synthetic-draft
```

这次运行会生成暂存文件、QA 报告、交付决策和应用计划。写入源码项目是独立步骤：必须先检查预演计划，再明确确认对应的运行 ID。

## 当前支持范围

### 已实现的通用适配器

| 格式 | 当前能力 |
| --- | --- |
| JSON 本地化文件 | 提取、重建和结构保护 |
| YAML / TOML | 面向本地化资源标量的提取与重建 |
| CSV / TSV / XLSX | 表格坐标、键列和非文本单元保护 |
| Markdown / HTML | 可见文本提取与重建；代码、属性以及 `script`、`style`、`svg` 内容保持不变 |
| Word OpenXML 文档 | `.docx`、`.dotx`、`.docm`、`.dotm` 可见文本提取与重建，按目标语言规范化字体，并执行确定性包结构 QA |
| SRT / WebVTT | 字幕 cue、时间轴和内联标记保护 |
| XLIFF 1.2 / 2.x | 单元 ID、源文本和内联 XML 结构保护 |
| GNU gettext PO/POT | 上下文、注释、复数、头部和占位符保护 |

### 实验性平台适配器

| 平台资源 | 当前边界 |
| --- | --- |
| Android `strings.xml` | 支持 `string`、`string-array`、`plurals`，并进行暂存、确定性 QA 和显式 opt-in 的 merged dependency resource overlay |
| iOS `.strings` / `.stringsdict` | 支持基础资源提取、重建和目标 `.lproj` 暂存 |
| Xcode `.xcstrings` | 支持 source language 单元和 variation leaf 的目标语言条目写入 |

适配器 ID、内容保留规则和完整格式边界见 [适配器契约](docs/adapters.md)。

## 工程证据

### v0.4.0 Word 文档本地化

v0.4.0 新增只依赖 Python 标准库的 Word OpenXML adapter 和 CLI 路径，支持 `.docx`、`.dotx`、`.docm`、`.dotm`。它本地化可安全编辑的可见 XML 文本，为译文 run 按目标语言规范化字体，保留非文本包内容，并校验宏字节不变且不执行宏。Workbench 可以把选择的文件、文件夹或拖拽文件复制到临时 project，再进入正常的暂存交付流程。

旧 `.doc`、加密或 malformed package、图片文字和嵌入对象内容不会被静默声称已完成本地化。

### v0.3.1 发布审计

v0.3.1 移除了 DeepSeek provider 中硬编码的私有环境文件路径，并要求 provider 凭据通过显式环境配置提供。发布审计通过了单元测试、协议验证、适配器契约验证、编译检查和公开回归脚本，也确认运行时代码中不存在已检查的私有本地路径模式。

详见 [v0.3.1 发布审计](docs/v0.3.1-release-audit.md)。

### v0.3.0 真实项目工作流强化

v0.3.0 新增只读检查摘要，并更新了 AntennaPod 一次性克隆项目的冒烟测试证据。该证据重点验证源文件不被意外修改、检查摘要可交付、受限合成草稿流程和可审查交付工件。它不声称已经验证 provider 真实翻译质量、破坏性应用流程或外部项目的完整生产级本地化。

详见 [AntennaPod v0.3.0 冒烟测试结果](docs/antennapod-smoke-test-results-v0.3.0.md) 和 [Android 真实项目压力矩阵](docs/android-real-project-stress-matrix.md)。

### v0.2.3 Android 资源可靠性

实验性 Android 适配器目前覆盖：

- `string`、`string-array` 和 `plurals`；
- 占位符、转义百分号，以及 `\n`、`\t`、`\'`、`\"` 等 Android 转义符；
- `<b>`、`<i>`、`<u>` 内联标记，以及只包含 `href` 属性的简单 `<a>` 链接；
- CDATA 边界和资源前的 XML 注释；
- 相互独立的源集（source set），以及符合 Android 顺序要求的资源限定符路由，包括 MCC/MNC 限定符；
- 盲测模式下的参考译文隔离，以及现有语言维护模式；
- 保留仅存在于目标语言文件中的旧资源；无法安全判断路径时会停止处理，不会猜测；
- 对不支持的复杂标记保持原样，并标记为 `owner_review_required`；
- 用于安排审核优先级的确定性风险元数据；这不是语义层面的译文质量评分。

具体支持结构、已知限制和明确排除能力见 [v0.2.3 Android 支持说明](docs/android-v0.2.3-support.md)。

### v0.2.1 运行模式基准

| 运行模式 | 参考策略 | 结果 |
| --- | --- | --- |
| `blind_benchmark` | `blind` | 通过：已有译文不会泄漏到生成文件中 |
| `greenfield_localization` | `style_only` | 通过 |
| `existing_locale_maintenance` | `preserve_existing` | 通过：保留 10 个文本段，生成 2 个文本段 |
| `rewrite_or_harmonization` | `tm_assisted` | 通过 |

合成 Android 测试项目包含 12 个源语言文本段和 10 个已有的 `zh-CN` 译文。基准测试同时验证：仅存在于目标语言中的资源不会被删除，源码文件的哈希值不会发生变化。

```bash
python benchmarks/v021-mode-system/run.py
```

### AntennaPod DeepSeek 实测

![AntennaPod 英语到日语和韩语 DeepSeek 基准：每种语言 869 个文本段，确定性 QA 未发现问题，编译成功](docs/assets/benchmark-antennapod.svg)

| 指标 | 日语（`ja`） | 韩语（`ko`） |
| --- | --- | --- |
| 源项目 | AntennaPod `develop` 分支 | 同左 |
| 文本段 | 869 | 869 |
| 批次 | 29 | 29 |
| 模型 | `deepseek-chat` | `deepseek-chat` |
| 确定性 QA | 0 个阻断问题，0 个警告 | 0 个阻断问题，0 个警告 |
| 编译 | `:app:assembleFreeDebug` ✓ | `:app:assembleFreeDebug` ✓ |

完整流程：提取 → 分批 → DeepSeek API → 汇总 → 暂存 → QA → 打包交付。如需在单独克隆的 AntennaPod 项目上复现这套检查流程，请参阅 [AntennaPod Android 冒烟测试指南](docs/antennapod-smoke-test.md)。

## 核心概念

当前真实架构和能力状态见 [Architecture](docs/architecture.md)。未来路线见
[Architecture Roadmap](docs/architecture-roadmap.md)；路线图不是当前 release 承诺。

### 运行模式

| 运行模式 | 适用场景 | 默认参考策略 |
| --- | --- | --- |
| `greenfield_localization` | 为项目新增目标语言 | `style_only` |
| `existing_locale_maintenance` | 维护已经审核的现有译文 | `preserve_existing` |
| `rewrite_or_harmonization` | 明确重写译文或统一表达风格 | `tm_assisted` |
| `blind_benchmark` | 在已有译文完全隔离的条件下进行评估 | `blind` |

### 项目记忆

Localize Anything 会在 `.localize-anything/` 目录中保存已经审核的翻译记忆、运行历史和项目配置。在现有语言维护模式下，只要源文本哈希没有变化，已经审核的译文就会在后续运行中继续保留，不会被重复翻译，也不会产生无意义改动。

### 审核与交付

```text
审核智能体 → 按范围审核确认 → 交付决策 → 应用计划 → 备份后应用
```

人工验收以文本段为单位。真正写入源码文件前，应用计划会列出每一项新建、替换、保持不变或发生冲突的文件操作。

![Localize Anything 架构分层：协议、运行时、智能体、适配器、源文件与交付](docs/assets/architecture-layers.svg)

## 不在支持范围内的能力

Localize Anything 目前不是：

- 提示词合集；
- 通用机器翻译接口的简单封装；
- 成熟的企业级翻译管理系统（TMS）；
- 完整的 HTML 解析器，也不能自动处理任意嵌套标记；
- Android layout、drawable、asset 的本地化工具；
- Gradle 编辑器或 APK 反编译工具；
- 语义层面的译文质量评分工具；
- 覆盖复数、性别、RTL/bidi、格式化、Unicode 和 fallback 行为的 locale-complete 实现；
- DOCX 布局或渲染页面保真度验证器；
- 译文所述现实世界事实的真实性验证器；
- 仅凭 provider 结果 intake、reconciliation 或确定性 QA 就声称完整 provider-backed quality 的工具；
- 在范围、审核和 signoff 不匹配时声称完整 knowledge-backed quality 的工具；
- 在非文本、动态、服务端、OS 或其他运行时表面未纳入源范围时声称完整产品本地化的工具；
- APK 或 IPA 重新打包工具；
- 专业人工审核的替代品；
- 会在没有确认的情况下改写代码库的工具；
- 自动执行破坏性 apply 的工具；
- 对“大模型输出无需证据即可直接上线”的承诺。

## 项目成熟度

Localize Anything 当前更适合作为开发者工具和本地化工程实验框架使用。它已经有可复现的结构验证、暂存交付和安全应用流程，但平台适配器仍在扩展中，语义层面的译文质量仍需要人工审校或更高等级的评审证据。

## 仓库结构

```text
protocol/         可移植的协议结构定义和生命周期规范
runtime/          Python 参考运行时
adapters/         适配器清单和入口
benchmarks/       公开基准测试项目和运行脚本
tests/            运行时单元测试和集成测试
docs/             公开文档
```

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
