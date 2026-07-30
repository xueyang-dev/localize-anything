# Memory And Context

## User-Facing Model

Keep two durable product concepts:

```text
Glossary
Project Memory
```

The storage representation may evolve, but do not make users maintain separate
term registries, term decisions, review-decision logs, and Knowledge Pack term
files as competing sources of truth.

Store durable project memory under `.localize-anything/` when appropriate. Ask
before committing project memory if it may contain private product information.

## Concept-Centered Glossary

Model the product concept first, then its expressions across locales:

```yaml
concepts:
  - id: workspace
    source_terms:
      en: [Workspace]
    translations:
      zh-CN:
        preferred: 工作区
        forbidden: [工作空间]
      ru:
        preferred: Рабочая область
    status: locked
    scope: product
    notes: Main space where users manage projects and runs.

  - id: cny
    source_terms:
      universal: [CNY]
    action: preserve
    status: locked
```

Entries may include source terms, per-locale preferred/forbidden translations,
`translate` or `preserve` behavior, status, scope, context, notes, provenance,
and human confirmation.

## First-Run Glossary Flow

```text
Discover -> Import -> Normalize -> Rank -> Confirm -> Use
```

- Discover existing glossaries, locale resources, README/product docs, repeated
  UI concepts, brands, code entities, Translation Memory, and prior decisions.
- Import canonical project data plus supported CSV, YAML, or JSON.
- Normalize duplicates and conflicting representations without discarding
  provenance.
- Rank approximately 5–15 high-impact concepts rather than asking the user to
  approve every low-risk term.
- Confirm preferred, forbidden, preserve, scope, and product-meaning decisions.
- Use approved concepts in generation and review.

Low-risk candidates may be provisionally accepted by the Agent and corrected
through later review. Locked or high-risk decisions require explicit evidence
or user confirmation.

## Translation Memory

Use project-level Translation Memory to:

- reuse confirmed complete sentences;
- detect source changes that make old targets stale;
- suggest similar reviewed copy;
- preserve human corrections;
- reduce duplicate work.

Prefer exact segment ID, exact source, compatible scope, and then conservative
fuzzy matching. Never mix target locales. Unreviewed generated text is reference
material, not authoritative memory.

## Style And Preserve Rules

Project Memory should also retain:

- audience and product voice;
- capitalization, punctuation, formality, and UI-length guidance;
- brands, codes, variables, URLs, product names, and other preserved forms;
- locale-specific conventions;
- recurring defects and accepted corrections.

## Context Construction

For each implementation or review batch, load only:

- product and user context;
- declared scope and candidate classifications;
- relevant Glossary concepts;
- relevant reviewed Translation Memory;
- relevant style and preserve rules;
- adjacent UI or document context;
- hard format constraints;
- unresolved high-risk decisions.

Do not treat chat summaries, embeddings, browser state, generated guesses, or
unreviewed model output as durable truth.

## Promotion

Promote information only after its scope and review status are clear:

- confirmed concepts and translations -> Glossary;
- reviewed complete targets -> Translation Memory;
- accepted voice and convention decisions -> style rules;
- recurring mistakes and corrections -> review history;
- unresolved ambiguity -> human confirmation, not memory.
