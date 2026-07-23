# Changelog

All notable changes to Project Comfy Gallery are recorded here.

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
