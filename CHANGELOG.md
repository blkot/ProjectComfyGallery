# Changelog

All notable changes to Project Comfy Gallery are recorded here.

## 0.1.0-rc.4 — 2026-07-24

Library navigation and structured-LoRA interpretation:

- Sort the Media Library by file time, import time, filename, or size; file time
  descending is the default.
- Filter the Media Library and saved review scopes by exact checkpoint and LoRA
  references, including historical workflow-only references.
- Traverse the current filtered and sorted library from Media Detail with
  Previous/Next controls, arrow keys, neighbor prefetch, position, and a
  context-preserving return link.
- Expand structured LoRA-loader values into one semantic observation per active
  entry while preserving the complete raw collection and strength evidence.
- Upgrade semantic extraction to `2.1.0`; existing workflow snapshots require one
  bulk reprocess to receive structured active-LoRA usages.

## 0.1.0-rc.3 — 2026-07-24

Bulk-scan reliability hotfix:

- Disable Dramatiq's ten-minute default actor limit for NAS scans so large imports
  are not interrupted and automatically replayed.
- Allow operators to opt into an explicit scan limit with
  `CG_SCAN_ACTOR_TIME_LIMIT_SECONDS`; `0` keeps long-running scans unlimited.

## 0.1.0-rc.2 — 2026-07-24

NAS import correctness hotfix:

- Prune QNAP, Synology, Windows, macOS, and freedesktop metadata directories before
  recursive source scanning.
- Preserve explicitly curated hidden directories that are not recognized system
  metadata.
- Add regression coverage for QNAP's `.@__thumb` image variants.

## 0.1.0-rc.1 — 2026-07-24

First release candidate of the local-NAS MVP:

- Media import, immutable originals, exact deduplication, and derivative generation.
- Embedded ComfyUI workflow evidence, node/model registries, and offline corrections.
- Blind manual evaluation with versioned criteria, resumable review, and revisions.
- Observational checkpoint/LoRA analysis with immutable saved runs.
- Portable exports, scheduled backup, guarded restore, worker recovery, and
  operational status.
- Hardened amd64 Docker deployment verified on the Intel J4125 NAS.
