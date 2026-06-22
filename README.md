# Localize Anything

<p align="center">
  <strong>面向真实代码库、支持智能体协作的软件本地化工程框架。</strong><br>
  <em>大模型可以生成译文；Localize Anything 负责让译文安全、可审查地进入交付流程。</em>
</p>

<p align="center">
  <a href="#localize-anything">简体中文</a> ·
  <a href="README.en.md">English</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="许可证：MIT">
  <img src="https://github.com/xueyang-dev/localize-anything/actions/workflows/ci.yml/badge.svg" alt="持续集成状态">
  <a href="https://github.com/xueyang-dev/localize-anything/releases/tag/v0.3.1"><img src="https://img.shields.io/badge/release-v0.3.1-blue" alt="当前版本：v0.3.1"></a>
  <img src="https://img.shields.io/badge/QA-deterministic-green" alt="质量检查：确定性规则">
  <img src="https://img.shields.io/badge/apply-staged%20first-blueviolet" alt="应用策略：先暂存，后写入">
</p>

Localize Anything 面向需要在真实代码库中开展本地化工作的开发者和本地化团队。
它不是简单的翻译脚本，而是一套可追踪、可审查、可复现的交付流程：先提取待翻译内容，
再由智能体（Agent）、模型服务或人工生成译文；随后使用确定性规则校验结构，将结果暂存
供人工审核；只有在明确确认运行 ID 后，才会把变更写入项目。

## 当前状态

**当前公开版本：** [v0.3.1 — Provider Path Hygiene Fix](https://github.com/xueyang-dev/localize-anything/releases/tag/v0.3.1)

v0.3.1 是一个向前修复版本，移除了 DeepSeek provider 中硬编码的私有环境文件路径，
并要求 provider 凭据通过显式环境配置提供。v0.3.0 则强化了真实项目工作流，新增
只读检查摘要，并更新了基于一次性克隆项目的冒烟测试证据。这两个版本未扩大本地化
功能边界；Android 功能范围仍以 v0.2.3 的支持说明为准。详见
[变更记录](CHANGELOG.md)、[v0.3.1 发布审计](docs/v0.3.1-release-audit.md)和
[真实 Android 项目压力矩阵](docs/android-real-project-stress-matrix.md)。

已经验证的工程结果：

- v0.3.1 干净发布审计通过
- 运行时代码私有路径卫生扫描通过
- 单元测试、协议验证、适配器契约验证、编译检查和公开回归脚本通过
- AntennaPod 一次性克隆项目的只读检查和冒烟测试通过，未修改已跟踪源文件
- Android 真实项目压力矩阵已记录 AntennaPod、NewPipe、Tusky 和 Fossify File Manager 的检查/合成流程证据
- v0.2.3 Android 资源可靠性回归检查通过
- v0.2.1 运行模式基准检查通过
- AntennaPod DeepSeek 实测覆盖日语、韩语两个目标语言，每种语言 869 个文本段；确定性
  QA 未发现问题，两个语言版本均编译成功

这些结果证明的是流程与结构检查的正确性，不等同于对译文质量的人工评价，也不表示
生成结果可以免审查直接上线。

## 为什么需要它

大模型可以生成读起来合理的文本，但真正的软件本地化交付还需要处理许多工程问题：
保护占位符和标记、保留已经审核的译文、记录处理证据、暴露冲突，并确保工具不会意外
破坏代码库。

Localize Anything 为代码库、智能体或人工译者与最终交付物之间提供工程保障。
运行时负责可由程序确定完成的工作，例如结构校验、暂存、冲突检查和变更应用；智能体与
翻译服务负责语义生成，人工审核负责最终判断。

## 工作流程

**提取 → 生成 → 校验 → 暂存 → 审核 → 应用**

- 从真实项目支持的资源格式中提取可翻译内容
- 根据运行模式决定哪些内容需要生成、哪些内容必须保留
- 通过宿主智能体或模型服务生成初稿，并严格限定可见上下文
- 使用程序检查占位符、标记、转义符、资源键和文件结构
- 在代码库之外暂存输出，供人工检查
- 打包清单、QA 证据、审核状态和应用计划
- 只有在明确确认运行 ID 后才应用变更，并在替换文件前创建备份

<p align="center">
  <img src="docs/assets/workflow-dark.svg" alt="Localize Anything 工作流：从项目智能体到备份后应用的九个步骤" width="900">
</p>

## 安全保证

| 保证 | 实现方式 |
|------|----------|
| **先暂存，后写入** | 生成文件写入隔离的暂存目录，不直接修改代码库中的文件。 |
| **确定性质量检查** | 使用程序检查占位符一致性、标记完整性、转义符、资源键和格式规则。 |
| **不静默覆盖** | 出现冲突时阻止应用，直到问题得到处理。 |
| **确认后应用** | 必须提供匹配的 `--confirm-run-id`；替换文件前会创建备份。 |
| **源文件变更检测** | 使用 SHA-256 检测运行期间出现的意外修改。 |
| **维护模式保留** | 在经过验证的维护流程中，保留未发生变化的已审核译文，以及仅存在于 Android 目标语言文件中的资源。 |
| **参考译文隔离** | 盲测模式不会让已有译文进入生成环节所使用的文件。 |
| **交付过程可审查** | 清单、QA 结果、审核确认范围和文件操作均可检查。 |

完整的安全设计见[安全说明](docs/security.md)。

## 快速开始

### 从源码安装

```bash
git clone https://github.com/xueyang-dev/localize-anything.git
cd localize-anything
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[yaml]"
python -m unittest discover -s tests -v
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

## 示例

下面的命令使用合成草稿，为 Android 源语言文件创建一份日语全新本地化的暂存交付包。
整个过程不会调用外部模型：

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

这次运行只会生成暂存文件和交付证据，不会直接写入项目。应用变更是一个独立步骤：
必须先检查预演计划，再明确确认对应的运行 ID。

## 支持范围

### 已实现的通用适配器

以下适配器在清单文件中标记为 `implemented`：

- JSON 本地化文件
- YAML 和 TOML
- CSV、TSV 和 XLSX
- Markdown 和 HTML 文本的提取与重建；代码、属性以及 `script`、`style`、`svg`
  中的内容保持不变
- SRT 和 WebVTT
- XLIFF 1.2 和 2.x
- GNU gettext PO/POT

### 实验性平台适配器

- Android `strings.xml`
- iOS `.strings` 和 `.stringsdict`
- Xcode `.xcstrings` 字符串目录

适配器 ID、内容保留规则和完整的格式边界见[适配器契约](docs/adapters.md)。

## 工程证据

### v0.2.1 运行模式基准

| 运行模式 | 参考策略 | 结果 |
|----------|----------|------|
| `blind_benchmark` | `blind` | 通过——已有译文不会泄漏到生成文件中 |
| `greenfield_localization` | `style_only` | 通过 |
| `existing_locale_maintenance` | `preserve_existing` | 通过——保留 10 个文本段，生成 2 个文本段 |
| `rewrite_or_harmonization` | `tm_assisted` | 通过 |

合成 Android 测试项目包含 12 个源语言文本段和 10 个已有的 `zh-CN` 译文。基准测试
同时验证：仅存在于目标语言中的资源不会被删除，源码文件的哈希值不会发生变化。运行命令：

```bash
python benchmarks/v021-mode-system/run.py
```

### v0.3.1 发布审计与路径卫生

v0.3.1 移除了 DeepSeek provider 中硬编码的私有环境文件路径，并要求 provider 凭据
通过显式环境配置提供。发布审计通过了单元测试、协议验证、适配器契约验证、编译检查
和公开回归脚本，也确认运行时代码中不存在已检查的私有本地路径模式。

详见 [v0.3.1 发布审计](docs/v0.3.1-release-audit.md)。

### v0.3.0 真实项目工作流强化

v0.3.0 新增只读检查摘要，并更新了 AntennaPod 一次性克隆项目的冒烟测试证据。该证据
重点验证源文件不被意外修改、检查摘要可交付、受限合成草稿流程和可审查交付工件。
它不声称已经验证 provider 真实翻译质量、破坏性应用流程或外部项目的完整生产级本地化。

详见 [AntennaPod v0.3.0 冒烟测试结果](docs/antennapod-smoke-test-results-v0.3.0.md)
和 [Android 真实项目压力矩阵](docs/android-real-project-stress-matrix.md)。

### v0.2.3 Android 资源可靠性

实验性 Android 适配器目前覆盖：

- `string`、`string-array` 和 `plurals`
- 占位符、转义百分号，以及 `\n`、`\t`、`\'`、`\"` 等 Android 转义符
- `<b>`、`<i>`、`<u>` 内联标记，以及只包含 `href` 属性的简单 `<a>` 链接
- CDATA 边界和资源前的 XML 注释
- 相互独立的源集（source set），以及符合 Android 顺序要求的资源限定符路由，
  包括 MCC/MNC 限定符
- 盲测模式下的参考译文隔离，以及现有语言维护模式
- 保留仅存在于目标语言文件中的旧资源；无法安全判断路径时会停止处理，不会猜测
- 对不支持的复杂标记保持原样，并标记为 `owner_review_required`
- 用于安排审核优先级的确定性风险元数据；这不是语义层面的译文质量评分

具体支持的结构、已知限制和明确排除的能力见
[v0.2.3 Android 支持说明](docs/android-v0.2.3-support.md)。

### AntennaPod DeepSeek 实测

<p align="center">
  <img src="docs/assets/benchmark-antennapod.svg" alt="AntennaPod 英语到日语和韩语 DeepSeek 基准：每种语言 869 个文本段，确定性 QA 未发现问题，编译成功" width="640">
</p>

| 指标 | 日语（`ja`） | 韩语（`ko`） |
|------|---------------|---------------|
| 源项目 | AntennaPod `develop` 分支 | 同左 |
| 文本段 | 869 | 869 |
| 批次 | 29 | 29 |
| 模型 | `deepseek-chat` | `deepseek-chat` |
| 确定性 QA | 0 个阻断问题，0 个警告 | 0 个阻断问题，0 个警告 |
| 编译 | `:app:assembleFreeDebug` ✓ | `:app:assembleFreeDebug` ✓ |

完整流程：提取 → 分批 → DeepSeek API → 汇总 → 暂存 → QA → 打包交付。

如需在单独克隆的 AntennaPod 项目上复现这套检查流程，请参阅
[AntennaPod Android 冒烟测试指南](docs/antennapod-smoke-test.md)。

## 核心概念

### 运行模式

| 运行模式 | 适用场景 | 参考策略 |
|----------|----------|----------|
| `greenfield_localization` | 为项目新增目标语言 | `style_only` |
| `existing_locale_maintenance` | 维护已经审核的现有译文 | `preserve_existing` |
| `rewrite_or_harmonization` | 明确重写译文或统一表达风格 | `tm_assisted` |
| `blind_benchmark` | 在已有译文完全隔离的条件下进行评估 | `blind` |

### 项目记忆

Localize Anything 会在 `.localize-anything/` 目录中保存已经审核的翻译记忆、运行历史和
项目配置。在现有语言维护模式下，只要源文本哈希没有变化，已经审核的译文就会在后续
运行中继续保留，不会被重复翻译，也不会产生无意义的改动。

### 审核与交付

```text
审核智能体 → 按范围审核确认 → 交付决策 → 应用计划 → 备份后应用
```

人工验收以文本段为单位。真正写入源码文件前，应用计划会列出每一项新建、替换、保持
不变或发生冲突的文件操作。

<p align="center">
  <img src="docs/assets/architecture-layers.svg" alt="Localize Anything 架构分层：协议、运行时、智能体、适配器、源文件与交付" width="640">
</p>

## 不在支持范围内的能力

Localize Anything 目前不是：

- 提示词合集
- 通用机器翻译接口的简单封装
- 成熟的企业级翻译管理系统（TMS）
- 完整的 HTML 解析器，也不能自动处理任意嵌套标记
- Android layout、drawable、asset 的本地化工具
- Gradle 编辑器或 APK 反编译工具
- 语义层面的译文质量评分工具
- APK 或 IPA 重新打包工具
- 专业人工审核的替代品
- 会在没有确认的情况下改写代码库的工具
- 对“大模型输出无需证据即可直接上线”的承诺

## 仓库结构

```text
protocol/         可移植的协议结构定义和生命周期规范
runtime/          Python 参考运行时
adapters/         适配器清单和入口
benchmarks/       公开的基准测试项目和运行脚本
tests/            运行时单元测试和集成测试
docs/             公开文档
```

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
