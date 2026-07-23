# ADR-0002: Immutable Media Identity and Exact Deduplication

**Status:** Accepted
**Date:** 2026-07-23

## Context

Media from different ComfyUI installations can share filenames while containing different bytes. Files may be renamed or moved. Similar AI-generated outputs should not be merged accidentally.

## Decision

- Assign each media record an internal UUIDv7.
- Calculate SHA-256 over original file bytes.
- Use SHA-256 for exact deduplication.
- Store filenames/paths only as source provenance.
- Preserve one immutable managed original for each exact content hash.
- Represent multiple locations as source occurrences.
- Do not use perceptual hash for MVP deduplication.

## Consequences

- Same filename/different content remains distinct.
- Renames and repeated copies do not duplicate evaluation records.
- Re-encoded or metadata-modified equivalents may remain separate; this is accepted.
- Managed storage can use content-addressed paths without exposing them as identity.

## Alternatives considered

- **Filename/path identity:** rejected because collisions and moves are common.
- **Perceptual hash deduplication:** rejected because small visual differences and workflow evidence may be significant.
- **Decoded-pixel hash:** rejected for MVP because it could merge files with different embedded workflows.
