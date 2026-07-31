# Localize Anything Phase 6：Documenso 俄语发布验收

**执行日期：** 2026-07-31
**目标应用：** Documenso（官方仓库的独立 clone）
**目标应用路径：** `/tmp/localize-anything-phase6-gwOiM6/documenso`
**目标分支：** `codex/phase6-ru-acceptance`（未推送）
**基线提交：** `6ec67d1c4db67812c737a30e40f8e0bd6086f920`
**目标语言：** `ru`
**Phase 6 判定（Phase 6.1 归属复核后）：** `release_candidate`

## 结论摘要

Documenso 的签署完成页已经完成一次可运行的俄语验收。Coding Agent 只使用 Localize Anything 的五个新命令完成扫描、Glossary、确定性检查、独立审查和报告；项目工程验证使用 Documenso 自己的 npm/Prisma/Biome 命令。浏览器中可以看到俄语 UI，分享对话框也已覆盖，语言 cookie、`Accept-Language` 检测和未知语言回退均可观察到。

Phase 6.1 的干净基线对照确认：`google.ts` 类型错误在未包含俄语改动的 checkout 中同样出现，是 Documenso 的 `pre_existing` 外部 blocker；本地化没有引入它。React hydration mismatch 只在之前的持久化 in-app browser stale context 中出现，干净 baseline 和本地化分支的 fresh Playwright context 均不复现，归类为 `unrelated_environmental`。3072 条空译文逐条核对后全部位于 excluded scope，受控完成页、认领表单和分享对话框的 28 个关联 entry 中有 0 个空译文。因此 Localize Anything 核心没有 false-ready、false-blocking 或本地化引入的 unresolved blocker，可以开始首个重构后版本的发布准备；Documenso 自身仍需单独处理其既有 build blocker。

完整归属证据见 [Phase 6.1 blocker attribution](./phase6-1-blocker-attribution.md)。

## 目标项目和验收范围

### 技术栈与基线

| 项目 | 结果 |
| --- | --- |
| 技术栈 | TypeScript、React Router v7、Hono、Prisma、Tailwind、shadcn/Radix、Lingui、tRPC、Playwright、Biome |
| Node/npm | Node `v22.23.0`，npm `10.9.8`；package metadata 要求 npm `>=11.11.0`、Node `>=22` |
| source locale | `en` |
| target locale | `ru`（本次加入 supported locales） |
| 资源位置 | `packages/lib/translations/en/web.po` → `packages/lib/translations/ru/web.po`，编译产物为 `web.mjs` |
| i18n 方案 | Lingui；服务端从 cookie 或 `Accept-Language` 加载 catalog，客户端动态激活 locale |
| 原生命令 | `npm run translate:compile`、`npm run prisma:generate`、`npm run test -w @documenso/lib -- --run`、`npm run build -w @documenso/remix`、Biome |
| 初始 Git 状态 | clone 后为干净工作树；验收改动只在目标应用分支，未推送 |

### 包含范围

本次只验收带 token 的签署完成流程：

- `/sign/:token/complete` 完成状态、动态文档标题和收件人卡片；
- `Share`、`Download`、`Go Back Home` 等入口和操作；
- 注册/认领表单：姓名、邮箱、密码、校验错误路径；
- 俄语 catalog 注册、语言 cookie、系统语言检测和 source fallback；
- 分享对话框中的标题、正文、分享文本、图片替代文字和操作按钮；
- 一次完整的 Localize Anything 五命令链路，以及人工确认门。

### 排除范围

未翻译整个 Documenso，也未把以下内容伪装成完成：已认证工作区、管理员/设置页、邮件模板、API/audit log、其他格式生态和全部 3127 条 UI message。数据库中的 `[MEDIUM] Document 2 - COMPLETED`、`Recipient 1`、邮箱等是动态用户/测试数据；它们不是系统预置文案。源码中没有 `Recipient 0` 的完成页显示问题，相关占位计数使用 1-based 逻辑。

## Localize Anything 命令记录

默认路径严格使用以下五个命令，其他命令均为项目原生命令：

```bash
localize scan /tmp/localize-anything-phase6-gwOiM6/documenso \
  --source-locale en --target-locale ru \
  --source packages/lib/translations/en/web.po
localize glossary bootstrap /tmp/localize-anything-phase6-gwOiM6/documenso
localize check /tmp/localize-anything-phase6-gwOiM6/documenso \
  --target packages/lib/translations/ru/web.po
localize review /tmp/localize-anything-phase6-gwOiM6/documenso \
  --target packages/lib/translations/ru/web.po
localize report /tmp/localize-anything-phase6-gwOiM6/documenso
```

结果：

- `scan`：通过；识别 117 个支持的资源文件，选中 gettext PO source，写入 project memory；没有生成旧平台 artifact。
- `glossary bootstrap`：通过；129 个 concept（120 个仍为 candidate、9 个 locked），状态 `ready_for_confirmation`。锁定 9 个高影响术语：Document completed、Document title、Email address、Go back home、Sign document、Signed、Signer、Upload、View document。
- `check`：`pass_with_warnings`；`blocking=0`、`actionable_warning=0`、`coverage_limitation=3072`、`known_or_expected=0`、`informational=0`。全部 3072 条属于 `translation_coverage`，来自受控范围之外的未翻译 catalog entries。
- `review`：先生成独立 packet（3127 个对齐 segment），再在新 context 中审查；2 条低严重度审查项自动放行，0 条 finding，0 条人工确认要求。
- `report`：核心报告仍显示 `needs_attention`，原因仅是上述 3072 条 coverage warning；Phase 6.1 已证明这些 warning 全部为 excluded scope，因此最终发布映射为 `release_candidate`，不是 false-blocking。

## Coding Agent 改动

目标应用中做了最小、聚焦的产品改动：

1. 在 `packages/lib/constants/locales.ts` 和 `packages/lib/constants/i18n.ts` 注册 `ru`。
2. 从 source catalog 提取更新 `packages/lib/translations/en/web.po`，新增 `packages/lib/translations/ru/web.po` 及编译后的 `web.mjs`。受控完成页/认领页和分享对话框翻译为俄语；完整 catalog 仍明确保留 3072 条未翻译项。
3. 将 `packages/ui/components/document/document-share-button.tsx` 中可见的分享文案接入 Lingui（外部 Tweet intent 的 payload 保留为外部分享协议，不视为 UI 漏翻）。

没有修改 Localize Anything 的 `core.py`、CLI、Runtime 或任何旧平台模块，也没有新增状态机、registry、plugin layer 或兼容 wrapper。

## 原生工程验证

| 命令 | 结果 | 说明 |
| --- | --- | --- |
| `npm ci` | 未通过（环境/依赖限制） | lockfile 缺少解析到的 `typescript@5.9.3`，且当前 npm `10.9.8` 不满足 package engine；随后用 `npm install --ignore-scripts --no-audit --no-fund` 完成干净依赖安装 |
| `npm rebuild skia-canvas --workspace @documenso/remix --foreground-scripts` | 通过 | 下载并安装当前平台 native binary |
| `npm run prisma:generate` | 通过 | Prisma client 生成成功 |
| `prisma migrate status` | 通过 | schema up to date |
| `npm run translate:compile` | 通过 | en/ru catalog 编译成功 |
| `npm run test -w @documenso/lib -- --run` | 通过 | 9 个文件，190 tests passed |
| `npx biome check packages/lib packages/ui apps/remix/app --max-diagnostics=20` | 通过（有既有 warnings） | exit 0；338 warnings、26 infos，无 error |
| `npm run typecheck -w @documenso/remix` | baseline 与本地化分支均未通过 | 两个 checkout 都在未修改的 `packages/lib/server-only/ai/google.ts:8` 报 `apiKey` 不存在于 `GoogleVertexProviderSettings`；归属 `pre_existing` |
| `npm run build -w @documenso/remix` | baseline 与本地化分支均未通过 | 两个 checkout 都在同一 Google Vertex 类型错误处停止；翻译 extract/compile 阶段已通过；归属 `pre_existing` |
| `npm run lint` | baseline 通过；本地化分支因生成 artifact 退出 1 | baseline 为 857 warnings/30 infos、无 error；本地化分支仅多出 `.localize-anything/deterministic-check.json` 和 `review-packet.json` 超过 Biome 1 MiB 输入限制，归属 `unrelated_environmental`；目标范围 Biome 检查两边均通过 |
| Playwright/E2E | 未运行 | clone 的认证/测试 fixture 不属于本次公开 token 完成页受控范围 |

## 运行时证据

实际启动 `npm run dev:remix` 并访问：

`http://localhost:3000/sign/evqzU3YQhyuq8d6TtEDf4/complete`

- `Accept-Language: ru-RU,ru;q=0.9` 返回 200、设置 `lang=ru` cookie，并出现 `Документ подписан`、`Все подписали документ`、`Поделиться`、`Скачать`、`Нужно подписать документы`。
- `POST /api/locale` 设置 `lang=ru`，随后携带 cookie 的请求仍返回俄语；cookie 为 HttpOnly、两年 Max-Age，证明刷新/重启路径有持久化依据。
- `Accept-Language: xx-XX,xx;q=0.9` 回退到英文 source catalog（`Document Signed`、`Share`、`Download`），没有空字符串或 raw key。
- 浏览器 document language 为 `ru`；完成页、认领表单和分享对话框均显示俄语，无 body 中的 `Error`。
- 动态 `[MEDIUM] Document 2 - COMPLETED`、`Recipient 1` 和邮箱按用户内容保留；未错误地将它们报告为系统文案。页面没有 `Recipient 0`。
- 分享对话框中已验证标题、隐私说明、分享文本、图片 alt 和按钮均进入 Lingui。
- fresh Playwright context 对 baseline 和本地化分支均未观察到 hydration mismatch；之前持久化 in-app browser 的 warning 不能在干净 context 复现，归属 `unrelated_environmental`，不构成 Localize Anything blocker。

证据截图：

- [俄语签署完成页](./phase6-documenso-ru.jpg)
- [俄语分享对话框](./phase6-documenso-share-ru.jpg)

## Review、确认门和 readiness 语义

独立 review context 使用 `review-packet.json`，不复用生成理由。最终 review 结果为 2 条 `auto_cleared`、0 条开放 finding、0 条 `human_confirmation_required`。

另外用临时测试 finding 验证确认门：

1. 开放 medium finding 后，report 变为 `needs_human_confirmation`，未确认不能 ready。
2. 对不存在的 finding 提交确认被拒绝（`Confirmation does not match an open human-review finding`）。
3. 对开放 finding 提交有效确认被接受；随后撤销测试缺陷并恢复空的 `human-confirmations.json`，最终报告没有遗留确认。

因此本次没有 false-ready。确定性 check 的 blocking 数为 0；3072 条 coverage warning 已聚合为 excluded scope，不会被错误升级成 false-blocking。`translatable=false` 等预期信息项没有在本次受控路径中阻断 ready。

## P0/P1/P2

| 等级 | 项目 | 判定 |
| --- | --- | --- |
| P0 | 错误 ready、目标 locale 读取、确认门失效、五命令阻断 | 未发现 |
| P1（外部） | Documenso baseline 与本地化分支共同出现的 Google Vertex 类型错误 | `pre_existing`，不归因于 Localize Anything；Documenso 发布前仍应修复或正式豁免 |
| P1（范围声明） | 受控范围外 3072 条 coverage limitation | 已聚合为 excluded scope，不是 actionable warning 或 false-blocking；扩大范围前必须重新翻译和审查 |
| P2 | `Reveal password` 的硬编码 aria-label、页面 metadata 的英文 title、外部 Tweet payload | 不影响本次可见受控流程；作为后续可访问性/metadata 清理项 |

## 最终发布判定

**`release_candidate`**

受控俄语流程可运行，核心测试、翻译编译、数据库生成/状态检查和目标范围 lint 通过；Localize Anything 的 review/confirmation 语义有效，没有 false-ready。Phase 6.1 已确认 build/typecheck 错误是 Documenso baseline 的 pre-existing 外部问题，hydration warning 是 unrelated environmental 现象，3072 条 coverage 已明确聚合到 excluded scope；这些不阻止 Localize Anything 进入首个重构后版本的发布准备。

Documenso 项目仍应单独修复或正式豁免 Google Vertex 类型错误；Localize Anything 本身不需要产品代码修改，也不应恢复旧 Runtime。
