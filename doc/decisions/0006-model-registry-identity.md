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
- Preserve every raw workflow reference while allowing a separate, reversible
  identity group for confirmed path/basename aliases.
- Automatically group references only when they resolve to the same canonical
  artifact. Basename-only similarity requires manual confirmation.
- Reject a group when its members resolve to different canonical artifacts.
- Expand confirmed groups in library/review filters and collapse them in analytics.

## Consequences

- Old media retains analytical value after model deletion.
- Local models are not penalized for lacking Civitai metadata.
- Reports must surface identity confidence.
- Filename inference remains correctable and cannot claim hash certainty.
- Alias confirmation changes interpretation only; workflows, usages, scores, and
  media do not need reprocessing.
- Revocation immediately restores the separate reference identities.

## Alternatives considered

- **Require hash for analysis:** rejected because many historical workflows would lose important factors.
- **Treat filename as canonical:** rejected because filenames can collide or be overwritten.
- **Silently collapse equal basenames:** rejected because two folders may contain
  different files with the same name.
- **Discard missing models:** rejected because it destroys historical explanatory data.
