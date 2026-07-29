# ADR-0011: Preserve Originals and Import Alternate Media Variants

**Status:** Accepted
**Date:** 2026-07-29

## Context

Apple spatial video is produced outside Comfy Gallery by an expensive conversion
pipeline. It belongs to the same logical gallery item as the source video, but it
is neither the workflow-bearing original nor a cheaply regenerable preview.
Replacing `MediaAsset` would break exact-byte identity, source history, and
embedded workflow ground truth. Storing it as a `Derivative` would incorrectly
claim the NAS worker can reproduce it.

Spatial-image presentation remains a Vision Pro runtime concern and does not
produce a stored backend file.

## Decision

- Keep `MediaAsset` as the one immutable original and canonical workflow source.
- Add `MediaVariant` for imported, non-regenerable alternate media bytes.
- Model Apple spatial video as the first variant role, `spatial_video`.
- Keep variant availability (`spatial_available`) separate from user intent
  (`prefer_spatial_playback`) and from `favorite`.
- Accept variants through a streamed, authenticated, idempotent command. Validate
  their bytes in the worker before managed placement and activation.
- Maintain at most one active variant for each media and role. Replacement becomes
  visible atomically only after the new file is ready.
- Keep ordinary preview, original, and proxy endpoints unchanged. Full-fidelity
  variant delivery uses a separate range-capable endpoint.

## Consequences

- One media retains one workflow, evaluation history, collection membership, and
  preference while clients choose among physical playback representations.
- A failed replacement cannot take a working spatial video offline.
- Stored spatial files participate in backup and storage accounting but not
  workflow parsing or original SHA-256 deduplication.
- The backend must periodically reconcile the cached availability projection with
  active ready variant rows.
- Future non-regenerable formats can add roles without changing original identity.

## Alternatives considered

- **Replace `MediaAsset` with a general asset table:** rejected because it turns a
  focused feature into a high-risk identity and ingestion rewrite.
- **Store spatial video as a derivative:** rejected because the NAS cannot
  regenerate it and clients intentionally request its full-fidelity bytes.
- **Create a second media record:** rejected because it would split evaluation,
  workflow, favorite, collections, and navigation for one logical generation.
- **Automatically switch existing playback endpoints:** rejected because browsers
  may not decode MV-HEVC and existing clients rely on ordinary playback semantics.
