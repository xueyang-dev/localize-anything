# Phase 2 live dry run

## Verdict

`pass_with_limitations`

Phase 2's default path was exercised end-to-end against a real application without using an old Localize Anything command or Runtime component. Two P0 defects exposed by the live UI audit--Gettext review mispairing and a false-ready report despite deterministic warnings--were fixed minimally and covered by regression tests. The result is suitable to begin the Phase 3 `KEEP / EXTRACT / REPLACE / LEGACY / DELETE` migration map. It is not a claim that Documenso now has complete release-ready Russian coverage.

## Target and scope

- Target: [Documenso](https://github.com/documenso/documenso), shallow clone at `6ec67d1` (`feat: rejected and expired recipient filters (#2889)`).
- Working copy: a temporary local Git worktree on `codex/phase2-ru-live-dry-run`; no commit or remote push.
- Stack: TypeScript/React Router (Remix) monorepo, Lingui PO catalogues, npm/Turbo, Biome, Playwright E2E.
- Source locale and resource: `en`, `packages/lib/translations/en/web.po`.
- Target locale and resource: `ru`, `packages/lib/translations/ru/web.po`.
- Localized product scope: the recipient signing result flow--completed, rejected, and expired states--plus the completion page's visible Share trigger and claim-account form, registration of Russian in the existing language picker, cookie persistence, `Accept-Language` detection, and English fallback paths.
- Excluded: the sharing dialog content after opening the Share trigger, signing-entry/auth flow, email templates, and the remaining application catalogue.

The Coding Agent added `ru` to the application's existing supported-language list and language labels, generated the Lingui Russian catalogue, translated 35 scoped messages, and ignored the local `.localize-anything/` state directory. The follow-up audit moved two hard-coded password-toggle labels into the existing Lingui path and corrected the medium-account seed's visible recipient numbering from zero-based to one-based. No new i18n abstraction, adapter, dependency, or complex Runtime behavior was added. Localize Anything received only the two minimal P0 corrections described below.

## Commands exercised

The Localize Anything path used only the five Phase 2 commands:

```bash
localize scan PROJECT --source-locale en --target-locale ru \
  --source packages/lib/translations/en/web.po
localize glossary bootstrap PROJECT
# Coding Agent edits the application with its native Lingui and npm commands
localize check PROJECT --target packages/lib/translations/ru/web.po
localize review PROJECT --target packages/lib/translations/ru/web.po
localize review PROJECT --target packages/lib/translations/ru/web.po \
  --findings .localize-anything/independent-review-residual-fix.json
localize report PROJECT
```

No old workflow command, Provider, Workbench, readiness report, work packet, Knowledge Pack, signoff record, or compatibility path was invoked.

Project-native validation commands:

```bash
npx --yes npm@11.11.0 ci
npm run translate:extract
npm run translate:compile
npm run lint
npm run build
npm run test:dev -w @documenso/app-tests -- --list
docker compose -f docker/development/compose.yml up -d database inbucket redis minio
dotenv -e .env.example -- npm run prisma:migrate-dev
dotenv -e .env.example -- npm run prisma:seed
dotenv -e .env.example -- npm run dev:remix
dotenv -e .env.example -- npm run test:dev -w @documenso/app-tests -- \
  e2e/envelopes/envelope-expiration-signing.spec.ts \
  --project=ui --grep "expired recipient is redirected to expired page"
```

## Results

### Scan and Project Memory

`localize scan` wrote only new-core state under `.localize-anything/` and selected the requested Lingui source catalogue correctly. Its broad inventory also identified 115 JSON/YAML/Gettext files, including repository configuration; the explicit `--source` selection kept the live run confined to the English web catalogue. No old Runtime artifact was generated.

### Glossary bootstrap

Bootstrap produced 119 candidates. Two high-impact decisions were locked:

- `Documenso` is preserved as the product brand.
- `Sign document` is translated as `Подписать документ`.

The remaining 118 candidates were deliberately left unconfirmed. In particular, a generic Russian term for a signing-role label was not locked without a real product decision.

### Product-native validation

- `npm run translate:compile`: passed.
- `npm run lint`: passed with 857 pre-existing warnings and 30 informational diagnostics; no errors after `.localize-anything/` was ignored.
- `npm run build`: passed. The full Turbo build ran the official Lingui extraction/compilation and Remix typecheck, and discovered the `ru` catalogue with 3,124 entries.
- `npm run test:dev -w @documenso/app-tests -- --list`: passed test discovery, finding 1,058 Playwright tests in 121 files.
- Docker development services, all Prisma migrations, and the native database seed completed successfully using the repository's `.env.example` values.
- The focused native Playwright test for an expired recipient redirect passed: 1 test, 1 worker, 0.8 seconds (3.6 seconds total command time).
- The Remix development server ran successfully at `http://localhost:3000` against the seeded PostgreSQL database.

### Residual-source classification

| Visible text | Classification | Source and result |
| --- | --- | --- |
| `Share` | System UI in the Lingui catalogue | `DocumentShareButton`; the Russian `msgstr` was empty and is now `Поделиться`. |
| Claim-account labels, placeholders, and CTA | System UI in the Lingui catalogue | Seven empty Russian entries were completed using the existing component messages. |
| `Reveal password` / `Mask password` | Hard-coded system accessibility UI | The shared `PasswordInput` now uses Lingui; Russian is `Показать пароль` / `Скрыть пароль`. |
| `Recipient 0` | Dynamic seed/test data | The completion route renders `recipient.name`. `medium-account-seed.ts` generated `Recipient ${r}` and now generates `Recipient ${r + 1}`; the live fixture displays `Recipient 1`. |
| `[MEDIUM] Document 2 - COMPLETED` | Dynamic seed/test data | It is the stored envelope title produced by the medium-account seed, not localizable system copy, so it is preserved. |

### Deterministic check

`localize check` returned `pass_with_warnings`:

| Classification | Count | Result |
| --- | ---: | --- |
| Blocking | 0 | Source and target catalogue structure matched; both locked glossary decisions passed. |
| Actionable warning | 1 | The generated Russian PO header lacks `Plural-Forms`; Lingui's ICU compilation passed, but this merits a project-level decision before broad plural coverage. |
| Coverage limitation | 3,089 | Intentionally untranslated catalogue entries outside the declared live scope. |
| Known/expected | 2 | The English envelope title and `Recipient 1` are dynamic test data rather than system translations. |

An initial check before the project's native `translate:extract --clean` reported 97 structural blocking items because the English and Russian catalogues were from different generated snapshots. Re-running the required native extraction synchronized them and reduced blocking to zero. This establishes the required order: native catalogue generation precedes `localize check`.

The pre-fix deterministic artifact explicitly reported the visible catalogue residuals, including `Share`, `Claim account`, `Name`, `Email address`, their placeholders, and password copy. This proves the check channel could detect those empty Russian targets. The hard-coded password-toggle labels were outside the catalogue and were found by live screenshot review; after moving them into Lingui, the current review packet contains all ten new source-target pairs. The post-fix check contains zero warnings for those ten entries and 3,090 warnings in total: 3,089 coverage limitations plus the plural-header warning.

### Independent review and confirmation gate

The first `localize review` packet exposed a P0 defect: Gettext entries from the same occurrence context could overwrite each other in the source-to-target lookup. For example, `Document Signed` was paired with the translation of a different completion sentence even though the PO file itself was correct. The live UI made the discrepancy observable.

The new core was corrected to include Gettext message identity (`msgctxt`, `msgid`, and plural source) in review matching. A regression test with two messages from the same occurrence context fails under the old behavior and passes after the fix. After regeneration, the packet paired all 35 non-empty targets correctly.

A fresh reviewer context then reviewed all 35 non-empty Russian targets, including the ten follow-up entries and 22 messages used by the completed, rejected, and expired routes. It recorded seven `auto_cleared` groups covering:

- completion, rejection, and expiration meaning and naturalness;
- visible Share and claim-account actions;
- identity, email, and password form terminology;
- password-toggle accessibility labels;
- dynamic test-data classification and the non-blocking PO plural-header warning.

Actionable translation findings: 0. Human confirmation required: 0.

Because no real finding required human adjudication, a temporary high-severity terminology-conflict fixture was used only to exercise the gate. `localize report --confirm` rejected a confirmation referring to a non-open finding, accepted one referring to the fixture's open finding, and then the fixture plus confirmation record were removed. The final review state contains only the independent review and no test defect. The core regression suite now passes seven tests, including the confirmation gate and both P0 cases.

### Live UI manual review

The seeded application was opened in an independent browser session, signed in with the repository's development account, and switched through the real language picker to `ru`. A hard reload preserved the selection and rendered `<html lang="ru">`, confirming the existing locale cookie path rather than a temporary client-only state.

The completed, rejected, and expired recipient-result pages were then opened against seeded records:

- completion: `Документ подписан`, `Все подписали документ`, the email-copy explanation, download, and return-home actions rendered naturally and without overflow;
- rejection: `Документ отклонён`, decision acknowledgement, owner-notification copy, and no-further-action copy were semantically consistent;
- expiry: `Срок подписания истёк` and the recovery guidance were natural and fit the desktop layout;
- all three route headings remained centered within a 1,280-pixel viewport with no horizontal document overflow.

The follow-up completion-page review confirmed `<html lang="ru">`, no horizontal overflow, a Russian `Поделиться` action, and fully Russian claim-account labels, placeholders, CTA, and password-toggle accessibility names. Toggling the password control changed its accessible action from `Показать пароль` to `Скрыть пароль`. The page no longer contains `Recipient 0`; it renders the corrected dynamic fixture name `Recipient 1`.

The remaining `[MEDIUM] Document 2 - COMPLETED` title and `Recipient 1` name are stored test data. Localizing them in the UI would corrupt user-controlled content, so they are documented as known/expected rather than translated. Opening the optional Share dialog reveals content outside this selected slice; that dialog and the rest of the application remain coverage limitations.

### Final report and release decision

Before this follow-up, `localize report` returned `ready` even though `localize check` had reported 3,098 warnings and the live page had obvious source-language fallbacks. This was recorded as a P0 false-ready defect. The minimal report rule now refuses `ready` while deterministic warnings remain; a Gettext untranslated-entry regression test fixes the behavior without adding orchestration or a state machine.

The rerun `localize report` returned `needs_attention`:

- deterministic blocking: 0;
- deterministic warnings: 3,090, classified above;
- independent review: 7 auto-cleared groups covering 35 non-empty targets;
- real findings: 0;
- human confirmations: 0 required, 0 recorded.

Release decision: do not claim a full Russian product release. The limited recipient-result and visible completion-page localization can move forward subject to ordinary product review; classifying or completing the remaining 3,089 catalogue entries, localizing any newly selected interactions such as the Share dialog, and running the service-backed Playwright suite are required for a broader release.

## Issues

### P0

- Fixed: Gettext review segments were matched only by context, so messages sharing one source occurrence could receive another message's target in the independent review packet.
- Minimal correction: include Gettext message identity in the review key while leaving other adapters unchanged.
- Fixed: the report mapped `pass_with_warnings` plus a completed review to `ready`, allowing visible untranslated UI to be hidden behind a warning count.
- Minimal correction: return `needs_attention` while deterministic warnings remain and document that those warnings must be classified before a release judgment.
- Regression evidence: `.venv/bin/python -m unittest tests.test_skill_phase2 tests.test_core_cli` passed 7 tests, including `test_review_pairs_gettext_targets_by_message_identity` and `test_report_is_not_ready_with_untranslated_warnings`.

### P1

- The target's native Lingui extraction must run before deterministic checking so both catalogues use the same source snapshot.
- The generated Russian PO has no `Plural-Forms` header. It does not prevent the native Lingui build, but should be resolved before translating plural-bearing screens broadly.
- A hard-coded password-toggle accessibility label escaped catalogue-only checking and was found by live UI review. It is now in Lingui, but the run confirms that page-level review remains necessary.
- The complete 1,058-test Playwright suite was not run; one scope-relevant service-backed test and live browser review were completed.

### P2

- `scan` inventories generic JSON/YAML files as potentially supported resources; explicit source selection is necessary for a focused project run.
- 3,089 untranslated entries are an intentional scope boundary, not findings in the translated recipient-result flow.
- The target repository has 857 existing lint warnings and 30 infos, none caused by this localization.

## Phase 3 readiness

Yes. The live path is now demonstrated as:

```text
scan -> glossary bootstrap -> Coding Agent localization -> native validation
-> check -> independent review -> confirmation gate -> report
```

It used only the new core command surface and did not make an old Runtime component an implicit fallback. Both blocking new-core defects found by the live application were repaired without adding orchestration or state-machine complexity. Phase 3 can therefore classify old modules from actual new-core and Skill call relationships rather than from hypothetical compatibility needs.
