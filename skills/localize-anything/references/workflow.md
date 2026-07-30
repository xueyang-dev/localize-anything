# Workflow

## Standard

```text
Product and repository preflight
-> Declared scope and completion criteria
-> Candidate classification
-> Glossary, style, preserve rules, and Translation Memory
-> Coding Agent implementation
-> Deterministic structural checks
-> Independent Agent review
-> Risk-ranked human confirmations
-> Review Report
-> Confirmed memory updates
```

Use Standard for a normal locale addition, an existing-locale update, or a
focused localization repair.

## Release

Release includes every Standard stage plus:

- primary-page target-locale screenshots;
- page/component semantic and visual review;
- actual project build and test results;
- locale switch, persistence, system/browser detection, and fallback checks;
- a clean Git diff;
- commit or pull-request preparation;
- promotion of confirmed results into Project Memory.

## Preflight

Identify:

- what the product is and who uses it;
- source and target locales;
- pages, components, files, resource types, and dynamic surfaces in scope;
- non-text and external surfaces that cannot be processed;
- existing i18n architecture and locale behavior;
- product concepts, style, preserve rules, and prior translations;
- project-specific completion requirements.

Bundle related blocking questions. Do not ask for information the repository
already answers.

## Candidate Classification

Classify every discovered candidate in scope:

- `translate`: requires a target-locale result;
- `preserve`: brand, code, identifier, universal label, or deliberate source
  form;
- `locale_format`: date, time, number, currency, unit, plural, or other value
  that belongs in locale-aware formatting;
- `developer_only`: logs, diagnostics, tests, or internal engineering text;
- `dynamic_external`: supplied by server, CMS, OS, dependency, or another
  runtime surface;
- `needs_context`: meaning cannot be decided safely yet.

Coverage is complete when every candidate in the declared scope is classified
and every `translate` candidate has a target result.

## Implementation

Use the project's existing i18n library, resource conventions, routing, tests,
and build system. The Coding Agent may add missing i18n architecture when the
task requires it, but Localize Anything does not prescribe a universal
framework.

Keep semantic batches coherent by screen, flow, component, document section, or
feature namespace. Preserve source provenance and adjacent UI context.

## Independent Review

Review from a context separate from generation. Provide source, target, relevant
Glossary concepts, style rules, UI context, screenshots, and deterministic
findings. Do not expose irrelevant generation rationale as evidence.

Review all three levels:

1. string;
2. page or component;
3. product concept.

## Completion

Return:

- declared and excluded scope;
- translated, preserved, formatted, developer-only, external, and unresolved
  candidate counts;
- deterministic check result;
- Agent review result;
- auto-cleared and human-confirmation counts;
- build/test and screenshot evidence required by the chosen depth;
- Git diff/commit/PR state;
- unresolved risks and next actions;
- confirmed Project Memory updates.
