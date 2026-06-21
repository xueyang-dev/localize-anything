# Public Introduction Draft

## English

I'm building Localize Anything — an agent-native localization framework focused
on safe, review-ready localization workflows rather than blind automatic
translation.

The project currently focuses on Android string resources and includes:

- structure-aware extraction for strings, arrays, and plurals;
- protection for placeholders, escapes, inline markup, CDATA, and comments;
- blind benchmark mode to prevent reference leakage;
- existing-locale maintenance mode for preserving reviewed translations;
- deterministic QA and CI-backed regression benchmarks;
- review-risk metadata for high-risk UI strings;
- a real-project smoke-test guide using AntennaPod.

The goal is not to “translate everything automatically.” The goal is to produce
traceable, reviewable localization delivery artifacts that developers can
inspect before applying changes.

Repo:
https://github.com/xueyang-dev/localize-anything

## 中文

我在做一个面向 Agent 的软件本地化框架：Localize Anything。

它不是“把所有文本丢给模型自动翻译”，而是更关注安全的本地化流程：资源提取、结构保护、翻译生成、人工审查、可复现验证和安全应用。

目前项目重点支持 Android string resources，包括：

- `strings`、`string-array`、`plurals`；
- placeholder、escape、inline markup、CDATA、XML comment 的结构保护；
- blind benchmark mode，避免参考译文泄漏；
- existing-locale maintenance mode，用于保留已经审查过的译文；
- deterministic QA 和 CI 回归基准；
- 高风险 UI 文本的 review-risk metadata；
- 基于 AntennaPod 的真实项目 smoke test 指南。

这个项目的目标不是取代人工审查，而是让 Agent 参与本地化时更安全、更可追踪、更适合开发者 review。

Repo:
https://github.com/xueyang-dev/localize-anything

## Short one-line versions

English:

> Localize Anything is an agent-native localization framework for safe,
> review-ready software localization workflows.

Chinese:

> Localize Anything 是一个面向 Agent 的软件本地化框架，用于构建安全、可审查、可复现的本地化工作流。

## Things not to claim

- fully automatic translation
- universal localization support
- production-safe operation without review
- complete Android app localization
- full HTML, layout, drawable, or asset support

