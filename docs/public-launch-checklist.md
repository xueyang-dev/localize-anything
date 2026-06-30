# Public Launch Checklist

## GitHub repository settings

Recommended About description:

> Agent-native localization engineering framework for traceable, review-ready
> delivery artifacts from source projects, user knowledge, model drafts,
> deterministic QA, and human review.

Recommended topics:

- `localization`
- `l10n`
- `translation`
- `android`
- `i18n`
- `ai-agents`
- `developer-tools`
- `automation`
- `quality-assurance`

Website:

- Leave it blank unless a real project page exists.
- Do not use an unrelated personal page.

These are repository-setting recommendations only. Apply them manually after
checking the public repository presentation.

## README first-screen check

The first screen should answer:

- What is this?
- Who is it for?
- What problem does it solve?
- Why is it safer than a simple translation script?
- How can someone try it quickly?
- What is stable versus experimental?

## Public claim boundaries

Safe claims, when supported by the linked documentation and current regression
evidence:

- agent-native localization framework
- safe localization pipeline
- Android resource reliability within the documented support boundary
- blind reference isolation
- existing-locale maintenance mode
- target-only obsolete preservation
- deterministic QA
- CI-backed regression benchmarks
- review-ready delivery artifacts
- real-project smoke-test guide
- architecture seeds clearly separated from stable release claims

Avoid claims of:

- fully automatic translation of any software
- production-safe translation without review
- complete Android app localization
- a full HTML parser
- layout, drawable, or asset localization
- Gradle editing
- APK decompilation
- universal support for all localization formats
- zero residual English or locale-complete support
- provider-backed quality from intake or QA alone
- knowledge-backed quality without scoped review/signoff
- DOCX layout/render fidelity or factual truth verification
- automatic destructive apply

## Pre-posting checklist

- [ ] Confirm README links work.
- [ ] Confirm the CI badge is green.
- [ ] Confirm the latest public release is v0.4.1.
- [ ] Confirm PR #25–#57 architecture seeds are not presented as stable release capabilities.
- [ ] Confirm the v0.2.3 Android support boundary is linked.
- [ ] Confirm v0.2.2 is not promoted.
- [ ] Confirm issue templates and `CONTRIBUTING.md` exist.
- [ ] Confirm the AntennaPod smoke-test guide is linked.
- [ ] Confirm no private roadmap or internal planning documents are tracked.
