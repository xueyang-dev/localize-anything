# 从旧平台 Runtime 迁移到 agent-native core

适用于 `0.5.0` 首个 agent-native core 发布准备。

## 发生了什么

Localize Anything 的产品边界从平台式 Runtime 收敛为 Coding Agent 的专业本地化
能力层。Agent 负责项目代码、资源、语言切换、build/test、截图和 Git；Localize
Anything 负责范围、Project Memory、concept-centered Glossary、确定性检查、独立
Review 和少量高风险确认。

默认路径只有：

```text
localize scan
→ localize glossary bootstrap
→ Coding Agent + 项目原生命令
→ localize check
→ localize review
→ human confirmation
→ localize report
```

## 用户可见的变化

### 改用五个新命令

旧项目或旧脚本应改为：

```bash
localize scan PROJECT --source-locale en --target-locale ru --source locales/en.json
localize glossary bootstrap PROJECT
# Coding Agent 使用项目原生命令修改代码和资源
localize check PROJECT --target locales/ru.json
localize review PROJECT --target locales/ru.json
localize report PROJECT
```

项目的 `npm test`、`npm run build`、`./gradlew test`、`xcodebuild`、截图和 Git
工作仍由 Coding Agent 直接执行；Localize Anything 不包装这些命令。

### 状态文件位置改变

新核心只读取和写入目标项目的 `.localize-anything/`，包括：

- `project-memory.json`；
- canonical `glossary.json`；
- `deterministic-check.json`；
- `review-packet.json` 与 `independent-review.json`；
- `human-confirmations.json`；
- `report.json`。

旧平台状态文件不会被新核心自动读取、升级或继续推进。需要复用旧术语、TM、风格
或决定时，必须由 Agent 选择性确认后导入 Project Memory/Glossary；不会再维护第二套
运行时术语真相。

## 已移除的用户入口

以下能力不再是产品入口，也不会被默认路径隐式调用：

- Provider 和 Provider handoff/generation 平台；
- Workbench、队列和 Web UI；
- workflow run、resume/recovery、readiness orchestration；
- signoff、release/document governance 和 Knowledge Pack pipeline；
- 旧 `localize-anything` CLI、旧命令、旧 artifact 状态和大协议目录。

这不是把旧命令改名为 wrapper；旧命令已经退出产品方向。只有用户明确要求维护旧项目
状态或兼容旧流程时，才可以在隔离的 compatibility path 中处理，不得让它成为默认路径。

## 格式和 Adapter 边界

核心命令优先覆盖 JSON、YAML/TOML、Android XML、Apple `.strings` / `.xcstrings`、
PO/POT 和 XLIFF。Markdown/HTML、CSV/TSV/XLSX、Word、SRT/WebVTT 和 Wesnoth 的
五个受限兼容 Adapter 方向仍可显式使用，但：

- 必须由 Agent 或用户明确选择；
- 只提供 manifest 中声明的解析、结构检查或 round-trip 能力；
- 不会因为格式缺口自动 fallback 到旧 Runtime；
- Adapter 存在不等于该格式拥有完整语义翻译支持。

格式不受支持时，让 Coding Agent 使用项目原生工具完成局部处理，并在 report 中记录
coverage limitation；不要退回整个旧平台。

## 迁移步骤

1. 移除旧 CLI、Provider、Workbench、workflow、readiness、signoff 和 Knowledge
   Pack 调用，不保留 deprecated shim。
2. 为一次具体任务声明 source/target locale、包含/排除范围和完成标准。
3. 初始化或审查 `.localize-anything/project-memory.json` 与 `glossary.json`。
4. 用五个命令完成 scan、Glossary、check、review 和 report；工程验证直接运行项目
   原生命令。
5. 让独立 Agent context 审查 `review-packet.json`，只把开放的高风险 finding 交给
   人工确认。
6. 把旧状态和旧报告作为历史材料保留在 Git 中，不把它们当作新核心的 readiness
   证据。

## 兼容性说明

`0.5.0` 仍处于 0.x，升级前应检查脚本和 CI 是否引用旧 CLI 或平台 artifact。新核心
不承诺读取旧状态文件；应用的 i18n 架构、语言切换、fallback、build/test 和产品
术语仍需要 Coding Agent 根据项目实际情况处理。
