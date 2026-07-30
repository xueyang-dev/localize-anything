# ADR 0001: Protocol-First, Workflow-Driven Architecture

## Status

Superseded by [ADR 0002](0002-coding-agent-localization-layer.md) on
2026-07-30. Retained as the historical v0.4 architecture decision.

## Decision

Build Localize Anything as an agent-native localization framework with four layers: portable protocol, reference runtime, agent integration, and adapter ecosystem.

Use a thin skill as the natural-language entrypoint. Use a lightweight CLI runtime for deterministic file operations. Keep adapter I/O language-neutral through JSON and JSONL contracts.

## Consequences

The project is larger than a standalone skill, but each layer remains replaceable. Inline localization can degrade gracefully without the runtime; standard project delivery requires deterministic runtime support.
