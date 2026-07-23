# ADR-0007: Versioned Manual Evaluation

**Status:** Accepted
**Date:** 2026-07-23

## Context

Manual scoring is expensive, criteria will evolve, and missing historical criteria cannot be reconstructed safely. Composite weights may change without changing the original judgment.

## Decision

- Store raw criterion scores as 0–10 integers, explicit N/A, or unset.
- Snapshot versioned evaluation templates.
- Preserve completed work when criteria/modules change.
- Keep score revision history.
- Treat Trash as reversible and separate from score.
- Calculate composite scores from versioned weighting profiles.
- Seed the locked V1 core/video/character rubric and anchors.

## Consequences

- Migrations never need to fabricate historical scores.
- Cross-version analysis must show coverage/shared criteria.
- Data model includes templates, criterion versions, revisions, and supplemental modules.
- Weight changes recalculate results without editing evaluations.

## Alternatives considered

- **Fixed columns on media:** rejected because criteria evolution would be destructive.
- **Store only overall score:** rejected because multi-angle analysis would be impossible.
- **Missing equals zero:** rejected because it corrupts both meaning and historical work.
