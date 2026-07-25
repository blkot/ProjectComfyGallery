# Changelog

All notable changes to Project Comfy Gallery are recorded here.

## Unreleased

## 0.1.0-rc.8 — 2026-07-26

- Add isolated one-command Mac development with native API/worker/web reload and
  separate PostgreSQL, Redis, credentials, ports, and media paths.
- Add annotated milestone validation and GitHub Actions publication of cached,
  attested `linux/amd64` images to private GHCR.
- Add guarded pull-only Xanta NAS deployment with backup, migration/drift
  preflight, version verification, and service health checks.
- Add page-wide and server-resolved all-matching Library scopes for review,
  collections, and tags.
- Add multi-checkpoint and multi-LoRA filters with explicit Any (OR) and All
  (AND) matching.
- Add a persistent collapsible icon navigation rail and preview-first, full-height
  Media Detail and Blind Review workspaces.
- Reorder Media Detail around filename/file facts, checkpoint and LoRA roles, and
  exact prompt text while moving UUID/SHA and parser internals into disclosures.
- Fit image and video viewers to the dynamic browser height with edge clearance,
  and move viewer/review navigation out of the media surface.
- Move compact file facts to the bottom of Media Detail and present exact prompts
  before checkpoint/LoRA evidence.
- Infer positive and negative prompt roles from conditioning-graph ancestry, honor
  explicit node mappings as overrides, and order positive prompts first without
  discarding negative or unclassified prompt evidence.
- Add a context-visible Evaluate panel to Media Detail with shared score controls,
  persistent Previous/Next panel state, and the same evaluation history as Blind
  Review.
- Add durable per-media optional evaluation modules; disabling a module hides it
  from active progress without deleting its scores or revisions.

## 0.1.0-rc.7 — 2026-07-25

- Use larger three-column gallery cards with a 2:3 portrait preview frame.
- Document the implemented bearer-authenticated import contract for a future
  ComfyUI save/upload custom node.
- Document targeted single-service deployments and the NAS build-cache cost model.

## 0.1.0-rc.6 — 2026-07-25

Collision-safe model-reference aliases:

- Detect path-qualified and basename-only checkpoint/LoRA references that may name
  the same file while preserving every exact embedded workflow value.
- Automatically group aliases only when they resolve to one canonical artifact;
  require confirmation for basename-only evidence and reject conflicting artifacts.
- Add confirm and undo controls to the Model Registry Duplicate aliases tab.
- Collapse confirmed aliases in Library filters and analytics, expand them in media
  and saved-review queries, and avoid media reprocessing or repeat evaluation.
- Reuse one Alpine package-index refresh per Docker hardening layer and support a
  configurable `ALPINE_MIRROR` to avoid slow or duplicate NAS build downloads.

## 0.1.0-rc.5 — 2026-07-25

LoRA Manager structured-value hotfix:

- Recognize the deployed LoRA Manager `__value__` collection wrapper instead of
  treating its complete object as one LoRA reference.
- Emit one semantic observation and model usage for each explicitly active named
  adapter while keeping inactive entries only in preserved workflow ground truth.
- Retain compatibility with the literal `**value**` wrapper documented in rc.4.
- Upgrade semantic extraction to `2.1.1`; affected existing workflows require
  reprocessing.
- Migrate the SPA from `react-router-dom` 7 to `react-router` 8.3.0 after the
  dependency audit identified a newly published high-severity advisory.
- Move release-only OCI labels after expensive Docker build layers so a version
  bump no longer invalidates unchanged OS and dependency caches.

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
