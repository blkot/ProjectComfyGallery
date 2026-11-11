# Changelog

All notable changes to Project Comfy Gallery are recorded here.

## Unreleased

## 0.1.0-rc.51 — 2026-11-11

- Add reversible archive and restore controls for custom Prompt Registry entries,
  preserving their historical media references.

## 0.1.0-rc.50 — 2026-11-11

- Register custom ComfyUI prompts with server-assigned Prompt Registry IDs and
  hand off the integration contract for Xanta Utils nodes.

## 0.1.0-rc.49 — 2026-11-10

- Add a Prompt source Library filter for API-prompt and visual-workflow prompt
  evidence, including saved scopes and media navigation.
- Replace the classifier-rating dropdown with a color-coded, single-select row
  for All, Safe, Sexy, Nudity, Explicit, and Review.

## 0.1.0-rc.48 — 2026-11-10

- Queue large all-matching AI classification selections in bounded requests and
  show batching progress in the Library.
- Add fixed-order classifier review queues so background classification results
  do not shift the active manual review sequence.

## 0.1.0-rc.47 — 2026-11-10

- Add a searchable Character LoRA filter to Library and carry its exact indexed
  scope through selection, review, saved filters, and slideshows.
- Keep classifier confidence scores read-only, highlight the model result, and
  make human review an optional override.

## 0.1.0-rc.46 — 2026-11-09

- Add human review for NSFW classifier suggestions, compact NudeNet evidence
  labels, and Library filters for classifier status and suggested rating.

## 0.1.0-rc.45 — 2026-11-09

- Add opt-in NSFW image classification with queued single and bulk actions,
  separate model assessments, optional NudeNet evidence, and idle model-process
  shutdown; add a standalone benchmark and manifest editor.
- Stabilize iOS viewer paging and refresh the visible media window after library
  mutations.

## 0.1.0-rc.44 — 2026-11-07

- Add the native iOS Photos-style Library, Viewer, and Prompt Registry flows, and
  add an exact Character LoRA filter to Library list and navigation APIs.
- Add Favorite and NSFW cues to Prompt Registry usage cards, keep Trash labels
  explicit, and simplify the Library page header.
- Improve Media Quick View responsiveness and keep the current image visible while
  a selected neighbor loads; add Prompt Registry index navigation and browser
  regression coverage for the viewer and responsive layouts.

## 0.1.0-rc.43 — 2026-11-06

- Add a source-preserving media quick view for Library and Prompt Registry, with
  shared media actions, context-aware navigation and slideshows, and grouped
  Prompt Registry usage APIs.

## 0.1.0-rc.42 — 2026-11-06

- Make persisted media content ratings default to SFW, remove the unmarked/clear
  states, and keep NSFW badges limited to explicitly marked media.
- Refine Library cards and controls with compact metadata rows, unified status
  badges, lazy preview decoding, and delayed sidebar auto-collapse.
- Widen the Prompt Registry layout and compress its heatmap for a denser view.

## 0.1.0-rc.41 — 2026-11-05

- Group Prompt Registry usage by character LoRA and split heatmap, lookup, and usage
  into a persistent two-column layout.
- Make the NAS deploy wrapper fail fast with an actionable error when the host is
  unreachable, and refuse to run when sourced into an interactive shell.
- Add `make release-prepare` to lock one version across every manifest, promote
  the Changelog, regenerate the OpenAPI snapshot, and reject unexpected file
  changes, with a dry-run mode.
- Derive release-version and health-check test fixtures from `VERSION` instead of
  hardcoding the current release.

## 0.1.0-rc.40 — 2026-11-04

- Fix the character-LoRA filter on random and stats: it now scopes the favorite
  signal instead of the candidate universe, so prompts never generated with the
  character remain eligible for `unmaterialized`.

## 0.1.0-rc.39 — 2026-11-04

- Extend the character-LoRA filter to random selection, stats, and lookup, with
  materialization evaluated inside the selected character scope.
- Remember the heatmap character-LoRA filter in browser storage and clear a stored
  value that no longer exists.

## 0.1.0-rc.38 — 2026-11-04

- Add a character-LoRA filter to the Prompt Registry heatmap, backed by a
  materialized `character_lora` value and a selector endpoint that lists the
  character LoRAs which currently have media.

## 0.1.0-rc.37 — 2026-11-04

- Index Prompt IDs for workflows that have no registered display profile by
  discovering `ShowText → XantaPromptLibrary` wiring in the API graph; the visual
  widget value is used only when exactly one distinct Prompt ID parses.
- Stop the active favorite star from disappearing when its card is hovered, move
  the Safety control next to Favorite in Media Detail, and keep the Prompt heatmap
  footer on a single line so hovering cannot change the panel height.


## 0.1.0-rc.36 — 2026-11-04

- Fix Prompt ID extraction for visual workflows whose ShowText widgets nest the
  promoted text in a list, so the visual snapshot wins over the stale API cache.
- Rebuild the materialized Prompt ID index after deploying the extraction fix.
- Remove workflow-parse and warning badges from Library cards; show a single-letter
  content-rating corner badge and a solid, high-contrast favorite star.
- Label the Media Detail favorite toggle and use solid fills for the active
  Favorite and SFW/NSFW controls.
- Keep the Prompt heatmap tooltip inside its panel and hide the panel scrollbars so
  hovering near an edge cannot reflow the matrix.

## 0.1.0-rc.35 — 2026-11-04

- Materialize Prompt Registry prompts from favorites instead of raw generation
  history: Trash outranks Favorite, so only a favorited, non-trashed media record
  materializes a prompt.
- Add `include_not_faved` and `include_trash` scopes to the Prompt Registry
  heatmap, defaulting to favorites outside Trash, and mark trashed media in
  lookup results with `is_trash`.
- Fix the Prompt Registry heatmap pointer offset caused by sizing the canvas from
  the padded wrapper instead of the canvas content box.
- Show trashed media greyed out in the Prompt Registry detail grid.
- Remember the Prompt Registry heatmap scope filters in browser storage, with a
  reusable persisted-state hook that ignores malformed or invalid preferences.

## 0.1.0-rc.34 — 2026-11-03

- Add a compact Prompt Registry contribution heatmap with source filtering,
  zoom, keyboard navigation, and click-through prompt resolution.
- Add a bounded heatmap API that reports per-prompt materialized media counts,
  including trashed generation history, with OpenAPI and client documentation.

## 0.1.0-rc.33 — 2026-11-03

- Add authenticated Prompt Registry source, random selection, materialization
  stats, and numeric neighbor lookup APIs.
- Track canonical prompt index keys so padded Prompt IDs share reliable media
  materialization semantics.
- Preserve the existing Prompt Registry UI navigation and document the new API
  contract in the OpenAPI snapshot.

## 0.1.0-rc.32 — 2026-11-02

- Optimize Prompt Registry bulk imports and source suggestions for large
  libraries, with durable media lookup indexing and a rebuild command.
- Preserve padded and 128-digit prompt indexes without integer overflow, and
  enforce the encoded import request-size limit on received bytes.
- Redesign Prompt Registry lookup around source/index selection and matching
  media navigation.

## 0.1.0-rc.31 — 2026-11-02

- Fix bulk Prompt Registry imports so responses are serialized from committed
  database rows instead of expired ORM instances.
- Document the Prompt Registry import contract, batching guidance, and safe retry
  behavior.

## 0.1.0-rc.30 — 2026-11-02

- Decouple reusable Prompt Registry definitions from media-specific Character
  LoRA and ordinary LoRA list evidence.
- Fix the Prompt Registry detail panel so an unselected prompt shows an empty
  state instead of an endless loading indicator.

## 0.1.0-rc.29 — 2026-11-02

- Prefer visual workflow widget values over stale API ShowText caches when
  resolving Prompt ID, Character LoRA, and related display fields.
- Add a source-index Prompt Registry with bulk import, media lookup, and a
  frontend registry page.
- Make Prompt IDs in Media Detail link to their registry lookup and matching
  media.

## 0.1.0-rc.28 — 2026-11-02

- Browse output-declared model, LoRA, prompt and prompt library fields in Media Detail.
- Migrate scoped character LoRA and prompt ID displays from existing Gallery
  snapshots without a live ComfyUI connection. Cached widget text stays explicitly
  unverified and separate from original evidence and model analytics.
- Recover enabled LoRAs from connected stackers; surface unresolved dynamic
  conditioning and cyclers without treating UI caches as execution results.

## 0.1.0-rc.27 — 2026-11-01

- Add SFW/NSFW/Unmarked media ratings, library filtering, card badges, detail
  controls, and bulk rating management with an indexed backend field.
- Add the photo-wall browsing route with adjustable row sizing and lazy loading
  for the current filtered image set.

## 0.1.0-rc.26 — 2026-11-01

- Add authenticated batch media archive downloads with queued worker jobs,
  collision-safe raw-original ZIP entries, and a single polled download link.
- Add explicit Library selection mode with cross-page selection, filter-backed
  scopes, per-card exceptions, and batch favorite/trash management.
- Add reversible bulk favorite and evaluation-trash API commands with preserved
  disposition revisions and updated OpenAPI contracts.

## 0.1.0-rc.24 — 2026-08-27

- Add a frontend-only Civitai post preparation page that defaults to
  `civitai.red`, maps parsed prompts, checkpoints, and LoRAs into an editable
  draft, and keeps credentials and publishing behind a future backend boundary.
- Add the ComfyUI workflow handoff bridge, preserve an already-open ComfyUI tab,
  and correct captured workflow-input media status messaging.
- Add XR slideshow playback with restored mount-time autoplay synchronization
  and refresh the native mobile and visionOS application icons.

## 0.1.0-rc.23 — 2026-08-16

- Preserve exact embedded workflow evidence while normalizing non-finite JSON
  numbers to `null`, preventing ComfyUI `NaN` values from blocking ingestion.
- Isolate workflow-snapshot persistence with a savepoint so metadata failures leave
  stored media usable as `ready_with_warnings` instead of stranded in processing.
- Show LoRA strengths separately in the web workflow inspector and improve Vision
  Pro spatial-video playback ownership and fallback behavior.

## 0.1.0-rc.22 — 2026-08-11

- Accept valid MPO/JPEG workflow input images and allow existing unsupported
  captures to be retried through the workflow-input resolve path.

## 0.1.0-rc.21 — 2026-08-10

- Shorten the Alembic 0014 revision identifier to fit PostgreSQL's standard
  32-character version column and add a repository-wide regression guard.

## 0.1.0-rc.20 — 2026-08-10

- Make MSS the owner of long-running GPU queue execution: ComfyGallery now performs
  one finite upload, persists the external batch, and completes its submission Job.
- Add bounded low-frequency and on-demand reconciliation, publish-only retry,
  migration-safe recovery, and durable MSS progress fields without resubmitting
  accepted GPU work.
- Treat validated CG spatial-variant activation as monotonic completion authority,
  including race-safe reconciliation and deterministic Media Detail refresh.

## 0.1.0-rc.19 — 2026-08-10

- Add ComfyGallery-driven ml-sharp-spatial conversion from video Media Detail,
  with durable per-media runs, active-run reuse, isolated worker capacity,
  restart/retry recovery, same-media publish verification, and persistent UI
  progress.
- Add the `0013_spatial_conversion_runs` migration, MSS server configuration,
  authenticated orchestration APIs, OpenAPI/client handoff, production worker and
  deployment health gates, and complete operational documentation.
- Enable audio during hands-off slideshow video playback.

## 0.1.0-rc.18 — 2026-08-09

- Capture workflow input images and videos into immutable SHA-256-deduplicated
  managed storage, with durable resolution jobs, authenticated APIs, and Media
  Detail presentation.
- Add a one-command milestone `ship` workflow, release-image waiting, actionable
  deployment planning, verified target-image backups, correct non-root backup
  ownership, retention warnings, and complete worker health gates.

## 0.1.0-rc.17 — 2026-08-06

- Add Hash-Search.

## 0.1.0-rc.16 — 2026-08-05

- Increase the ordinary media import limit from 128 MiB to 256 MiB.

## 0.1.0-rc.15 — 2026-08-04

- Add complete-library case-insensitive keyword search across current positive and
  negative prompts, checkpoint and LoRA references, confirmed aliases, and resolved
  model names, with the same URL-backed scope preserved through pagination, Media
  Detail navigation, slideshows, saved filters, collections, tags, and review
  sessions.
- Add accessible copy controls for exact extracted prompts, including secure-context
  Clipboard API support, a legacy browser fallback, and visible copied/failure
  feedback.
- Add automatic NAS deployment planning that selects no-op, isolated web-only, or
  immutable full-release paths from the deployed image revisions and local changes,
  with frontend verification, rollback, backup, migration, and health safeguards.
- Add visionOS playback of stored Apple spatial MV-HEVC variants, including
  preference-aware ordinary fallback, local variant caching, AVKit expanded spatial
  presentation, and reversible ordinary/spatial switching in the existing viewer.

## 0.1.0-rc.14 — 2026-08-03

- Treat re-uploading the exact active spatial-video bytes to the same media as an
  idempotent terminal duplicate outcome, without revalidating or storing a second
  file, while retaining cross-media duplicate protection.
- Present both new duplicate outcomes and historical duplicate-conflict audit rows
  as already attached/imported in Media Detail instead of spatial validation
  failures, and refresh affected media/job caches.

## 0.1.0-rc.13 — 2026-08-03

- Isolate critical media imports and spatial-variant validation from scan,
  workflow, registry, and maintenance work using two bounded Dramatiq worker
  pools, preventing long registry reprocessing from starving uploads.
- Give the background pool a separate runtime heartbeat path while retaining the
  critical media worker as the readiness signal.

## 0.1.0-rc.12 — 2026-08-03

- Upgrade the backend and worker runtime to FFmpeg 8.1.2 on Alpine 3.24 so
  standards-compliant Apple spatial videos containing extended projection metadata
  pass container inspection, with an image-build regression fixture for the exact
  formerly rejected structure.
- Add authenticated spatial-variant attachment from Media Detail, including
  `.mov` selection, validation progress, failure details, and retry behavior.
- Add a server-resolved, filter-preserving hands-off slideshow with randomized or
  ordered playback, neighboring-media preloading, keyboard control, and fullscreen.
- Improve Library workflows and preserve their filters and navigation context.

## 0.1.0-rc.11 — 2026-07-30

- Add immutable source-bound media variants with a durable lifecycle, atomic
  activation/replacement, reconciliation, backup-aware managed storage, and
  independent spatial playback preference.
- Accept streamed spatial-video uploads through authenticated APIs, validate Apple
  MV-HEVC metadata and both HEVC layers fail-closed, and serve active variants with
  HTTP byte-range support.
- Project canonical spatial availability, preference, and active-variant facts
  through list/detail APIs while retaining the deprecated spatial preference alias
  during the client migration window.
- Update the web Library and Media Detail to distinguish user playback preference
  from verified spatial-video availability without changing ordinary original,
  preview, or playback behavior.
- Publish a deterministic OpenAPI handoff, client changelog, migration-safe data
  model, ADR, operational guidance, and real Apple fixture regression coverage.
- Pin the backend to Alpine 3.23 with FFmpeg 8 and require multiview HEVC decoder
  capability during image construction.

## 0.1.0-rc.10 — 2026-07-28

- Add the native SwiftUI mobile client for authenticated gallery browsing,
  resumable blind review, image/video viewing, and reliable queued evaluation
  writes.
- Persist independent per-media Favorite and spatial-view preferences with safe
  false defaults, additive list/detail contracts, and idempotent update APIs.
- Filter the Library, context-preserving navigation, saved filters, bulk scopes,
  collections, tags, and review sessions by Favorite or spatial preference.
- Add Favorite controls and spatial indicators to the web Library and Media
  Detail while leaving device-generated spatial objects in the XR client.

## 0.1.0-rc.9 — 2026-07-26

- Skip unsupported GitHub repository attestations for a user-owned private
  repository while retaining BuildKit SBOM and provenance data in GHCR.

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
