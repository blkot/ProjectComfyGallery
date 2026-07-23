# ADR-0004: Layered Workflow Interpretation

**Status:** Accepted
**Date:** 2026-07-23

## Context

ComfyUI workflows vary across core versions, custom nodes, model architectures, and output nodes. A parser that stores only selected fields would lose evidence and require destructive reparsing when assumptions change.

## Decision

Use four layers:

1. Immutable embedded metadata.
2. Generic nodes, inputs, values, and connections.
3. Versioned semantic observations and corrections.
4. Evaluation and analytics.

Higher layers may be regenerated but never rewrite lower layers.

## Consequences

- Unknown workflows remain useful.
- Parser improvements can reprocess history.
- Storage and schema are more involved than a flat key/value table.
- Every analytical feature can trace back to source evidence.

## Alternatives considered

- **Flat extracted key/value metadata:** rejected because complex multi-model workflows lose roles and topology.
- **Raw JSON only:** preserves evidence but cannot support filtering/analysis.
- **Architecture-specific tables only:** brittle as new workflows and custom nodes appear.
