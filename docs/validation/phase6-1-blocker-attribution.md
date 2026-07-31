# Phase 6.1：外部 blocker 归属与发布收口

**执行日期：** 2026-07-31
**目标项目：** Documenso
**本地化分支：** `/tmp/localize-anything-phase6-gwOiM6/documenso`，`codex/phase6-ru-acceptance`
**干净基线：** `/tmp/localize-anything-phase6-gwOiM6/documenso-baseline`，detached `6ec67d1c4db67812c737a30e40f8e0bd6086f920`
**本地化范围：** `/sign/:token/complete` 的俄语完成页、认领表单、分享对话框和 locale 行为

## 结论

Phase 6.1 结论为：

- `google.ts` 类型错误是 `pre_existing`，干净 baseline 和本地化分支均复现，且该文件没有本地化 diff；它是 Documenso 的外部 blocker，不是 Localize Anything blocker。
- hydration warning 是 `unrelated_environmental`：之前只在持久化 in-app browser 的 stale context 中观察到；fresh baseline 和 fresh localized Playwright context 均没有 hydration mismatch。两者都能以 HTTP 200 渲染目标页面。
- 3072 个未译 segment 全部属于声明的 excluded scope。受控完成页/认领表单/分享对话框关联的 28 个 PO entry 中，空译文为 0 个。
- Localize Anything 的 blocking、actionable warning 和开放 finding 均为 0，确认门有效，没有 false-ready 或 false-blocking。

因此 Phase 6 最终收口为 **`release_candidate`**，可以开始首个重构后版本的发布准备。这个结论不等于 Documenso 应立即发布：Documenso 仍需独立处理其 baseline 已存在的 Google Vertex 类型错误。

## 基线方法

基线 worktree 从本地化分支的父提交创建，开始时没有源代码改动。为保持运行条件一致：

1. 复制同一 `.env` 和数据库/服务配置。
2. `npm ci` 在两个 checkout 都受 package lock 与 npm engine（当前 npm `10.9.8`，项目要求 `>=11.11.0`）限制，因此两个 checkout 都使用 `npm install --ignore-scripts --no-audit --no-fund`，再执行 `npm rebuild skia-canvas --workspace @documenso/remix --foreground-scripts`。
3. 两边均执行 `npm run prisma:generate`，避免未生成 Prisma client 把测试结果误判为本地化回归。
4. 运行结束后，baseline 的 PO 变化是 Lingui build 生成物；没有把它们视为源代码差异。目标本地化 worktree 只保留 ru 注册、en source catalog、ru catalog 和分享文案改动。

## 命令对照

| 检查 | clean baseline | localized checkout | 归属 |
| --- | --- | --- | --- |
| `npm run test -w @documenso/lib -- --run` | 9 files / 190 tests passed | 9 files / 190 tests passed | 无回归 |
| `npm run translate:compile` | pass | pass | 无回归 |
| `npm run prisma:generate` | pass | pass | 无回归 |
| `npm run typecheck -w @documenso/remix` | 同一 `google.ts:8` `TS2353` | 同一 `google.ts:8` `TS2353` | `pre_existing` |
| `npm run build -w @documenso/remix` | 在同一 Google Vertex 错误处停止 | 在同一 Google Vertex 错误处停止 | `pre_existing` |
| `npx biome check packages/lib packages/ui apps/remix/app --max-diagnostics=20` | exit 0，338 warnings/26 infos | exit 0，338 warnings/26 infos | 无回归 |
| `npm run lint` | exit 0，857 warnings/30 infos | exit 1；仅新增未跟踪 `.localize-anything/deterministic-check.json`（2.9 MiB）和 `review-packet.json`（5.5 MiB）超出 Biome 1 MiB 文件限制，另有 857 warnings/32 infos | `unrelated_environmental` workflow artifact |

### google.ts 归属

文件 `packages/lib/server-only/ai/google.ts` 在两个 checkout 都是同一内容：

```text
Object literal may only specify known properties, and 'apiKey' does not exist in type 'GoogleVertexProviderSettings'.
```

该错误在 Prisma 生成后、独立 baseline build/typecheck 和 localized build/typecheck 中都出现。`locales.ts`、`i18n.ts`、PO catalog 和分享按钮改动没有触及该文件或其类型依赖。因此标记为 `pre_existing`，不应修改 Localize Anything core，也不应把它记录为本地化引入的 P0/P1。

## 应用启动与 hydration 对照

### HTTP/页面

- baseline 在 `http://[::1]:3100/sign/evqzU3YQhyuq8d6TtEDf4/complete` 返回 HTTP 200；由于 baseline 没有 `ru` catalog，`Accept-Language: ru-RU` 正确回退到英文 source locale。
- localized checkout 在 `http://[::1]:3000/sign/evqzU3YQhyuq8d6TtEDf4/complete` 返回 HTTP 200；`Accept-Language: ru-RU` 返回俄语完成页。
- 两边 fresh headless Playwright context 都加载了目标页面，没有 body crash。API 资源的 403/AppError 是测试数据库认证路径的既有噪声，不是 hydration mismatch，也没有改变页面文本。

### hydration 归属

Phase 6 之前的持久化 in-app browser 曾记录：

```text
Warning: Did not expect server HTML to contain a <div> in <html>…
Hydration failed because the initial UI does not match…
```

这条记录不能在新 baseline 或 localized Playwright context 复现；两边均得到稳定的 SSR/客户端页面，俄语分支的 `html lang="ru"` 也正常。它与浏览器持久化 session、旧 dev server 状态或 in-app browser 环境相关，标记为 `unrelated_environmental`。本次不修改产品代码、不修改 Localize Anything，也不把它作为 Localize Anything 发布 blocker。

## 3072 个 segment 的范围归类

本次没有静默把 warning 数量改成零，而是以 PO location 和受控页面路径重新核对：

- `packages/lib/translations/ru/web.po` 有 3127 个 entry，其中 55 个有俄语译文，3072 个为空。
- 受控路径（`apps/remix/app/routes/_recipient+/sign.$token+/complete.tsx` 和 `packages/ui/components/document/document-share-button.tsx`）共关联 28 个 entry；空译文为 **0**。
- 所有 3072 个空译文聚合为 `excluded_scope`，不再逐条计入 actionable warning；确定性 check 仍如实报告 `warning_count=3072`，report 通过范围声明解释它们。

按 entry location 的互斥聚合如下：

| excluded scope bucket | 数量 |
| --- | ---: |
| authenticated workspace / shared components | 2349 |
| server / library / audit content | 237 |
| other Remix routes | 172 |
| email templates | 153 |
| shared UI outside the controlled flow | 142 |
| other generated or support locations | 19 |
| **合计** | **3072** |

这些内容不属于本次声明的签署完成页、认领表单、分享对话框或 locale 流程；若未来扩大范围，必须重新建立 scope、Glossary、check 和 review，而不是继续沿用本次 release candidate 的声明。

## 五命令与 readiness 复核

Phase 6.1 重新运行了：

```bash
localize scan …
localize glossary bootstrap …
localize check …
localize review … --findings /tmp/phase6-independent-review.json
localize report …
```

结果仍为：scan pass、glossary 129 concepts/9 locked、check `pass_with_warnings`（0 blocking、0 actionable、3072 coverage）、独立 review 2 条 auto-cleared/0 open finding、human confirmation 0。临时开放 finding 的确认门已在 Phase 6 验证过：未确认会阻塞，错误 finding ID 会拒绝，有效确认才会接受，测试 finding 已撤销。

核心 report 的原始状态仍为 `needs_attention`，但唯一原因是已被证明为 excluded scope 的 coverage warning。按 Phase 6.1 的归属规则，最终发布状态为 `release_candidate`，而不是 false-blocking。

## 发布收口

| 条件 | 结果 |
| --- | --- |
| clean install 与五命令链路 | 通过既有 Phase 5/6 证据；本次五命令复跑通过 |
| 新核心旧 Runtime 依赖 | 未发现；默认路径仍只有五个命令 |
| 本地化引入 build/typecheck blocker | 否；错误在 baseline 已存在 |
| 本地化引入 unresolved hydration warning | 否；fresh contexts 不复现，旧观察归为环境噪声 |
| 声明范围 blocking/actionable/open finding | 全部为 0 |
| excluded scope 聚合 | 3072 条完整保留并明确记录 |
| false-ready / false-blocking | 均未发现 |

**最终判定：`release_candidate`。**

可以开始首个重构后版本的发布准备。发布准备不包括替 Documenso 修复外部 Google Vertex 类型错误；该问题应由目标应用单独跟踪和复测。
