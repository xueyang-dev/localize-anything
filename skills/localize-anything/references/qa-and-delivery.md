# QA And Delivery

## Three Quality Channels

Keep these channels separate.

In the default path, `localize check` owns deterministic findings, `localize
review` creates and records the independent review, and `localize report`
summarizes both channels plus explicit human confirmations.

### Deterministic Checks

Mechanical tools may verify:

- resource structure and keys;
- placeholder and markup preservation;
- escapes, identifiers, and explicit preserve rules;
- source/target correspondence;
- declared-scope candidate classification and coverage;
- obvious source-language residuals that are not classified;
- source mutation and unsafe overwrite conditions.

Passing these checks does not prove semantic quality.
Do not report `ready` while deterministic warnings remain. Classify each
in-scope warning as blocking, actionable, a coverage limitation, or
known/expected before making a release judgment.

### Agent Review

Use an independent context to assess:

- semantic accuracy;
- natural target-language expression;
- terminology and product-concept consistency;
- tone, voice, and UI convention;
- omissions and unintended additions;
- page/component context;
- screenshot-visible results;
- cultural or locale adaptation.

Record finding, location, reason, risk, confidence, and suggested action.

### Human Confirmation

Route only decisions that genuinely need product ownership:

- official product-concept translations;
- brands and proprietary names;
- high-risk ambiguity;
- wording that may change product meaning;
- decisions the Agent cannot infer from repository evidence;
- final release judgment.

`localize report --confirm` accepts only decisions for findings still marked
`needs_human_confirmation`. Do not manufacture, auto-confirm, or silently
close those findings.

## Risk Routing

Auto-clear low-risk items only when the reason is visible and no hard constraint
failed. Never auto-clear:

- placeholder, markup, key, or file-structure damage;
- a conflict with a locked Glossary concept;
- unresolved legal, medical, financial, regulatory, or safety wording;
- meaning-changing ambiguity;
- missing required project build/test or Release evidence.

## Review Report

Report at least:

```text
Declared scope
Excluded and external surfaces
Translated items
Agent-reviewed items
Auto-cleared items
Human confirmation required
Human-edited after review
Deterministic blockers and warnings
Build/test results
Screenshot/page review results
Git diff / commit / PR state
Unresolved risks and next actions
Project Memory updates
```

Do not collapse deterministic, Agent, and human evidence into one quality score.

## Git Delivery

Use Git as the delivery and collaboration surface:

- inspect pre-existing user changes;
- keep localization changes reviewable;
- summarize affected files and resource counts;
- run checks against the actual diff;
- avoid destructive overwrite or deletion;
- prepare a commit or pull request only when requested or required by Release
  depth;
- leave unresolved high-risk decisions visible.

Release depth requires a clean, understandable diff—not necessarily an empty
worktree when the user already has unrelated changes.

## Memory Update

The Phase 2 default path records user confirmations through `localize report
--confirm`. It does not create a parallel update path for older memory assets.
When a confirmed Glossary or Project Memory change is needed, propose the
smallest scoped change for the user to review; do not present an unreviewed
draft as durable memory.

Only confirmed and reusable knowledge is eligible for a later memory update:

- approved product concepts and locale expressions;
- reviewed Translation Memory;
- accepted style decisions;
- preserve rules;
- recurring defects and their corrections.

Do not promote unreviewed drafts, low-confidence guesses, or a broad rule derived
from one narrow example.
