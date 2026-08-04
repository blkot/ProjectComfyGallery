# Frontend Information Architecture and UX

**Status:** Accepted

## Product areas

The frontend has two primary workspaces:

1. **Library and records** — manage media, metadata, registries, imports, errors, and analyses.
2. **Review** — evaluate media fluently with configuration hidden.

The application is desktop-first for a LAN workstation browser. Responsive behavior should remain functional on smaller screens, but phone-first review is not an MVP goal.

## Route map

Implemented routes and reserved later-phase route names:

```text
/login
/dashboard
/library
/library/:mediaId
/collections/:collectionId
/imports
/jobs
/registries/models
/registries/nodes
/review
/review/:sessionId
/analysis
/analysis/:runId
/settings
```

Implemented in Phase 1: `/dashboard`, `/library`, `/library/:mediaId`, `/imports`,
`/jobs`, and `/settings/tokens`.

Phase 2 extends `/library`, `/library/:mediaId`, and `/imports` in place with workflow
status/filtering, evidence/graph inspection, reprocessing, and missing-snapshot
backfill. Raw workflow payloads are fetched only after an explicit detail-page action.

Phase 3 implements `/registries/models` and `/registries/nodes`. Both pages use
master/detail panels rather than separate detail routes so search/filter position is
retained while correcting records.

Phase 4 implements `/review` and `/review/:sessionId`, and extends `/library` with
evaluation/Trash filtering, selection, collection/tag creation, saved filters, and
review-scope actions. `/collections/:collectionId` remains a later dedicated detail
route; Phase 4 collection selection is available from review home.

Phase 5 implements `/analysis` and `/analysis/:runId` with live report configuration,
immutable history, linked reruns, exact-value tables, training-step/matrix
visualizations, and media drill-down.

## Global shell

- Persistent primary navigation.
- Desktop navigation can collapse to an icon rail and remembers the preference in
  browser storage. Every icon retains an accessible route name and hover title.
  Compact layouts use the horizontal navigation independently of that preference.
- Global search.
- Current background-job indicator.
- User/session menu.
- Clear offline/degraded integration indicators.
- Toasts for transient success only; durable errors live in pages/panels.

## Library

### Gallery view

- Server-paginated grid (48 records per page in Phase 1; virtualization remains an
  option if measured gallery behavior requires it). Previous/Next and direct
  one-based page navigation are duplicated above and below the grid. A page change
  brings the start of the new grid into view.
- Three larger cards per ordinary desktop row, expanding to four on extra-wide
  displays, with a default 2:3 portrait preview frame matching common 1024×1536
  generations. Narrow layouts remain responsive.
- Deterministic server sorting by file time, import time, filename, or byte size.
  Newest file time is the default. For NAS sources, file time is the latest active
  source occurrence modification time; browser uploads fall back to the media import
  time.
- Thumbnail/poster and media-type indicator.
- Evaluation state and warning badges.
- Selection with keyboard modifiers.
- Multi-select actions for collection/tag/review.
- Progressive image loading, fixed aspect-ratio placeholders, and off-screen
  rendering containment for the larger cards.

### Table view

- Virtualized or server-paginated records.
- Configurable columns.
- Useful fields: UUID fragment, type, dimensions/duration, processing state, evaluation state, checkpoints/LoRAs, source count, warning/error count.
- Filename may be displayed as provenance but is never identity.

### Filter system

On wide desktop layouts, the complete filter system and Review scope actions occupy
the **Library controls sidebar**, a sticky, independently scrolling right sidebar
beside the gallery. Its visual scrollbar remains hidden, and it collapses to a
persistent icon rail using a locally remembered preference. The gallery and its
pagination use the remaining content width. When the viewport cannot support both
columns comfortably, the controls return to a full-width collapsible row above the
grid.

Gallery pagination is duplicated above and below the cards. Each instance combines
Previous/Next, a compact numbered window centered on the current page, first/last
page access with ellipses for long ranges, and a direct one-based page jump. Every
page change remains URL-backed and scrolls the gallery boundary into view.

The first Library control is an explicit complete-library keyword search. It accepts
checkpoint names and aliases, LoRA names and aliases, or positive/negative prompt
text, then submits the trimmed term as `q`; it never filters only the downloaded
gallery page. Search and Clear preserve unrelated filters and sort while resetting
pagination and the prior return-card anchor. Because `q` remains in the URL-backed
view context, refresh, copied links, numbered pagination, Media Detail traversal,
saved filters, server-resolved scopes, and filtered slideshows reproduce the same
population. The control announces searching and match counts, and distinguishes
keyword-specific failure and zero-result states.

The Library header also opens a focused **Start slideshow** dialog. The user chooses
the current filtered result or one collection, an image duration, and optional
shuffle. Start requests browser fullscreen within the initiating click and opens a
presentation-only route without the application navigation shell. Images advance on
the chosen timer; videos autoplay muted and advance when playback ends, with a
duration-based fallback if playback stalls. The playlist loops until Exit, while
Pause and Exit controls fade after pointer inactivity and reappear on interaction.
The browser receives at most 2,000 lightweight playlist records and loads media bytes
only for the active and next item. Starting or leaving a slideshow does not create a
Review Session or mutate evaluation/library state.

Filters include:

- Media type.
- Processing/readiness state.
- Evaluation state and Trash.
- Favorite, spatial playback preference, and stored spatial-video availability.
- Source root/path.
- Collection/tag.
- Architecture family.
- Pipeline pattern and usage slot.
- Checkpoint/LoRA/series.
- Workflow/node parse state.
- Registry confidence/ambiguity.
- Date, dimensions, duration, codec/container.
- Generic extracted configuration values where supported.

Filter chips show active state. Complex filters use a validated expression model suitable for saving.

The implemented multi-select checkpoint and LoRA selectors are backed by `model_reference`
identities rather than only current artifacts. Deleted, renamed, private, and
workflow-only historical references remain filterable. Confirmed aliases collapse
into one selector option with a combined usage count, while unconfirmed references
remain separate. Within one model dimension, the user explicitly chooses Any (OR) or
All (AND), with Any as the default. Different dimensions remain conjunctive: for
example, a checkpoint condition and a LoRA condition must both match.

The Model Registry includes a Duplicate aliases tab. It shows basename-derived
candidates, their exact raw aliases and usage counts, disables conflicting candidates,
and requires confirmation unless all members already share one canonical artifact.
Confirmed groups can be undone without reprocessing media.

### Scope actions

From current results or selection:

- Start review.
- Create/add to static collection.
- Apply/remove tags.
- Save current filter.
- Export selected metadata.
- Retry eligible processing stages.

The Library keeps explicit checkbox selection across pagination and filter changes
while the route remains mounted. It also provides Select page, Select all matching,
and Clear selection. Select all matching captures the current validated filter and
resolves collection/tag membership or review candidates on the server; the browser
does not download thousands of UUIDs. A collection is an exact membership snapshot
at action time, whereas a saved filter remains a reusable query that can match future
imports.

Each gallery card provides an independent Favorite star that does not open or
select the card. The web gallery distinguishes **Spatial preferred** (user intent)
from **Spatial ready** (a validated stored video variant). It does not claim that an
image preference proves successful XR runtime generation. Favorite, preference, and
availability filters remain in the URL, so Media Detail Previous/Next traversal uses
the same population and server-resolved scope actions preserve all conditions.

## Media record

The media record exposes:

Media Detail is a fixed-height workstation on desktop. The original image/video stage
occupies the complete left side below a dedicated control row containing library
return, deterministic Previous/Next traversal, position, and download. Controls never
overlay the media. The stage uses the dynamic browser viewport and a definite
containment box so every edge of an image or video remains visible across browser
sizes, zoom levels, and source aspect ratios. The right inspector scrolls
independently, so the media never moves out of view while workflow evidence is
inspected.

Inspector information is deliberately ordered by practical recall value:

1. original filename and readiness;
2. exact unsanitized prompt observations, with positive/main first and negative
   prompts retained but collapsed by default;
3. resolved checkpoint and LoRA usages, including pipeline slot and raw reference;
4. generation parameters;
5. parser diagnostics, node graph, raw evidence, sources, and derivatives;
6. UUID and SHA-256 in a collapsed technical-identity section;
7. compact dimensions, format, duration, size, and source file time at the bottom.

The right side has two mutually exclusive panels selected beside the filename:

- **Info** contains the evidence inspector described above.
- **Evaluate** contains the current media's core criteria, per-media optional-module
  switches, exact prompts, save state, Trash/restore, and Undo.

The selection is represented by `panel=evaluation` in the Media Detail URL. It is
preserved across Previous/Next traversal and refresh, but removed when returning to
the Library or requesting the server-side navigation population. The right pane
remains independently scrollable in either mode.

The heading also provides a canonical spatial-playback preference control for both
images and videos. Video detail reports stored spatial availability and active
variant facts separately. The browser preview deliberately remains on the ordinary
`playback_url`; it never attempts to silently replace browser-compatible media with
MV-HEVC.

Video detail also exposes a focused **Attach spatial video** panel beside those
variant facts. The panel accepts QuickTime MOV and compatible MP4-family files,
shows the selected filename and byte size, and requires a separate confirmation
before upload. It sends a fresh idempotency key with the source media hash, then
distinguishes upload, background validation, success, and failure while polling the
variant-import status. If a ready variant already exists, the panel explains that
the old file remains active until the replacement is fully validated. Successful
activation refreshes Media Detail, library, navigation, and job projections without
changing Favorite, spatial playback preference, ordinary browser playback, original
download, or workflow evidence. Failed validation keeps the selected file available
for an explicit retry with a new command key. Image detail never renders this panel.

### Preview

- Original image or video player.
- Original codec, versioned proxy derivative, and original download. A more explicit
  in-player proxy badge is a small follow-up.
- Zoom/pan for images.
- Poster, seek, volume, playback rate, frame stepping if practical for video review.

### Library viewing navigation

Media Detail viewing is separate from blind Review:

- Opening a gallery card carries the current filter, sort, and page context in the
  URL, so refresh, history, and copied links remain deterministic.
- Previous and Next query the complete filtered/sorted population rather than only
  the 48 cards on the current page.
- The browser updates the remembered gallery offset when traversal crosses a page
  boundary, so “Media library” returns to the target card's page.
- The detail URL also remembers the current media as a UI-only return anchor. Returning
  to the Library scrolls that exact card into view and highlights it without sending
  the anchor to media-list or navigation APIs.
- Left/Right arrow keys mirror Previous/Next unless focus is in an editable control.
- Neighbor detail data is prefetched on pointer hover or keyboard focus.
- The header shows the current one-based position and total population.

Direct detail links without explicit context use the default all-media,
newest-file-time view.

### Identity/provenance

- Media UUID.
- Exact SHA-256.
- Original byte size and detected type.
- Every source occurrence and source state.
- Original filenames/paths.
- Derivatives and recipes.

### Workflow

- Exact prompt fields.
- Raw embedded metadata viewer.
- Generic graph/node/edge viewer.
- Semantic observation list with confidence and source.
- Parser/extractor versions and errors.
- Optional “open/export embedded workflow” action where technically valid.

### Model usage

- Pipeline pattern.
- Ordered checkpoint usage slots/pair.
- LoRAs and training-series steps.
- Canonical/historical/ambiguous identity labels.
- Raw embedded references.

### Evaluation

- State and Trash disposition.
- Current scores and template.
- Revision history.
- Info/Evaluate switch beside the filename.
- Shared score controls and autosave behavior with Blind Review.
- Core module always active; optional Character module enabled per media.
- Disabling an optional module hides it without deleting scores or revisions.
- Open in blind Review when configuration-hidden scoring is preferred.

Blind Review uses the same full-height left media stage and independently scrolling
right control pane. It does not reuse the Media Detail evidence inspector: checkpoint,
LoRA, and configuration evidence stay hidden under EVAL-017. Session exit and progress
controls live in the right pane rather than obscuring the review media.

## Import and jobs

### Browser import

- Multi-file selection/drop zone.
- Preflight file counts and obvious unsupported types.
- Durable batch creation.
- Immediate navigation away without cancelling work.

### Source scans

- Configured roots.
- Last scan and current progress.
- Manual rescan.
- Counts for new, skipped, duplicates, missing, and failed.
- Drill-down to individual entries.

### Workflow backfill and upgrades

The Imports page provides two explicit workflow actions:

- **Process unparsed media** queues only records without a workflow snapshot.
- **Reprocess all workflows** queues every record after a semantic extractor upgrade
  or other global interpretation change.

Both actions use durable jobs, skip media with an already queued/running extraction,
and never rewrite originals or embedded ground truth.

### Job center

- Active, failed, retryable, and completed jobs.
- Stage and progress.
- Per-stage structured error.
- Retry and cancel-request actions where safe. Pause is not implemented because
  cooperative cancel plus retry is the clearer durable state model for MVP.
- Worker/integration health.

## Model registry

Views:

- Artifacts.
- Historical references.
- Ambiguous links.
- LoRA series.
- Comparison sets.
- Synchronization history.

The UI visually separates:

- Identity evidence.
- File availability.
- Civitai enrichment.

It must never imply that “no Civitai match” means a local model is invalid.

Phase 3 implements artifact/reference/series/comparison-group tabs, staged sync
history, manual artifact/reference corrections, and LoRA series rename, step, merge,
and split controls.

## Node registry

Views:

- Confirmed mappings.
- High-confidence active inferences.
- Needs-review suggestions.
- Unknown definitions.
- Schema variants.

Unknown inbox ordering:

1. Number of affected media.
2. Analytical impact.
3. Confidence.

Correction flow:

- Inspect evidence and examples.
- Select semantic tag/input.
- Preview affected workflows.
- Confirm and enqueue reprocessing.

Phase 3 implements the unknown-definition filter, schema/mapping detail, and manual
input mapping. Saving a mapping enqueues versioned reprocessing. Example raw-node
collections, graph-neighborhood previews, and arbitrary visual rule composition remain
enhancements rather than prerequisites for Phase 4.

## Review workspace

**Implementation status:** Complete in Phase 4. See
[Phase 4 manual evaluation and review](../development/phase-4-manual-evaluation.md).

### Layout

```text
┌──────────────────────────────────────┬─────────────────────────────┐
│                                      │ Prompt fields               │
│                                      │                             │
│         Image viewer /               │ Criterion 1   [slider] [×] │
│         video player                 │ Criterion 2   [slider] [×] │
│                                      │ ...                         │
│                                      │ Trash  Undo  Save status    │
│                                      │ Previous        Next        │
└──────────────────────────────────────┴─────────────────────────────┘
```

- Preview and criteria panes scroll independently.
- Preview gets the majority of horizontal space.
- Next media may prefetch.
- Session position is neutral and informational.

### Blindness boundary

Visible:

- Media.
- Exact prompt fields.
- Rubric and session position.

Hidden:

- Checkpoints, LoRAs, pipeline, settings, source/collection/tags, and experiment data.

### Controls

- Nullable 0–10 integer sliders.
- Clear button and Delete/Backspace.
- Explicit N/A control.
- 0/5/10 anchor guidance.
- Visible autosave state.
- Undo.
- Reversible Trash.
- Explicit Previous/Next.

No scoring or Trash action automatically advances.

### Resume entry

Review home proposes:

- Resume N In progress evaluations.
- Resume recent review sessions.
- Start random.
- Start from selection/collection/folder/filter.

It does not pressure the user with streaks, deadlines, or mandatory completion counts.

## Analytics workspace

**Implementation status:** Complete in Phase 5. See
[Phase 5 model-focused analytics](../development/phase-5-model-analytics.md).

Flow:

1. Define/filter the population.
2. Choose one supported report.
3. Choose criteria or weighting profile.
4. View summary, distribution, uncertainty, coverage, and warnings.
5. Drill into source media.
6. Save immutable run or rerun a previous analysis.

Charts must:

- Show sample count.
- Be navigable without relying only on color.
- Expose exact values/table equivalents.
- Avoid ranking language that implies causality.
- Mark insufficient cells/groups clearly.

## Loading, empty, and error states

Every page distinguishes:

- Loading.
- Empty because no data exists.
- Empty because filters exclude all data.
- Partial/degraded data.
- Recoverable error.
- Permission/session expiration.

Long operations return job IDs rather than indefinite spinners.

## Accessibility

- Keyboard navigation for all interactive elements.
- Visible focus.
- Semantic labels for sliders/N/A/clear.
- Sufficient contrast.
- Captions/labels for charts.
- No color-only state distinction.
- Respect reduced-motion preference.

## Frontend performance

- TanStack Query for server-state caching and invalidation.
- Virtualization for large grids/tables.
- Stable thumbnail dimensions to avoid layout shift.
- Pagination/cursors for records and events.
- Route-level code splitting.
- Avoid loading raw workflow JSON in gallery responses.
- Media range requests and browser caching.
- Prefetch only the next review candidate and essential metadata.

## Security

- Render prompts and metadata as text, not `innerHTML`.
- Sanitize filenames only for display safety, not semantic rewriting.
- Do not expose host filesystem absolute paths unless the API explicitly chooses an administrator-only representation.
- Use authenticated media URLs and range endpoints.
- Do not store bearer API tokens in browser local storage.
