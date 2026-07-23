# ADR-0008: Observational Model-Focused Analytics

**Status:** Accepted
**Date:** 2026-07-23

## Context

The user wants to discover tendencies in real generated media, not conduct strict benchmark experiments. Prompts and use cases may differ substantially. Primary interest is checkpoint and LoRA behavior.

## Decision

- Use user-selected filters to define the population.
- Describe associations/tendencies, not causality.
- Do not prompt-match or prompt-balance by default.
- Focus MVP reports on checkpoints, pairs, LoRAs, training steps, checkpoint-by-LoRA, and LoRA combinations.
- Preserve other workflow settings as filters.
- Show distributions, uncertainty, coverage, and effect sizes rather than a simple winner.
- Save exact immutable analysis datasets and score revisions.

## Consequences

- Results answer practical “when involved” questions.
- Reports require explicit interpretation guardrails.
- Confounding is described through co-occurrence/context rather than silently adjusted.
- The application avoids unnecessary experimental-design complexity.

## Alternatives considered

- **Strict matched prompts/configurations:** rejected for MVP because it does not match the user’s desired use and would discard much historical data.
- **Simple average ranking:** rejected as misleading.
- **Automated benchmark evaluators:** deferred because they are unnecessary and unsuitable for the CPU-only NAS.
