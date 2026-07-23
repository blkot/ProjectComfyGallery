# ADR-0006: Canonical and Historical Model Registry

**Status:** Accepted
**Date:** 2026-07-23

## Context

Workflow model references are commonly filenames, current LoRA Manager records may contain hashes, private models have no Civitai match, and historical files may be deleted.

## Decision

- Separate canonical artifact, raw workflow reference, workflow usage, and provider enrichment.
- Treat identity evidence, file availability, and enrichment as independent.
- Prefer hashes, but allow reversible unambiguous filename inference.
- Preserve ambiguous and workflow-only historical references.
- Allow historical references in analysis with visible provenance.
- Use LoRA Manager as the primary current inventory adapter.

## Consequences

- Old media retains analytical value after model deletion.
- Local models are not penalized for lacking Civitai metadata.
- Reports must surface identity confidence.
- Filename inference remains correctable and cannot claim hash certainty.

## Alternatives considered

- **Require hash for analysis:** rejected because many historical workflows would lose important factors.
- **Treat filename as canonical:** rejected because filenames can collide or be overwritten.
- **Discard missing models:** rejected because it destroys historical explanatory data.
