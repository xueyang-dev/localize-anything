# Benchmark Metrics

## Structural

- POT and generated PO parse successfully.
- Entry and context coverage.
- Placeholder and format-token parity.
- Plural-form agreement with the target header.
- Adapter source-context resolution rate.
- Rebuild and package hash integrity.

## Localization

- Accuracy and omission findings by severity.
- Terminology consistency across batches.
- Character voice and relationship consistency.
- Cultural adaptation findings with evidence.
- Human edits per 1,000 source words or segments.

## Context Efficiency

- Input, output, and cached tokens.
- Tokens per accepted segment.
- Working-packet size and trim events.
- Cross-batch consistency with and without durable memory in controlled runs.

## Incremental

- Correct classification of unchanged, changed, moved, new, and deleted units.
- Unnecessary retranslations of unchanged units.
- Stale-target detection and targeted repair coverage.

Report dimensions separately. Do not collapse them into a single quality score.
