# Product Requirements

**Status:** Accepted

Requirement IDs are stable. If a requirement is removed, its ID is retired rather than reused.

## Authentication

- **AUTH-001:** The system MUST provide one administrator login.
- **AUTH-002:** The web application MUST use an authenticated session.
- **AUTH-003:** The system MUST support revocable bearer tokens for machine clients.
- **AUTH-004:** The MVP MUST NOT implement registration, invitations, roles, or multi-user permissions.

## Media identity and storage

- **MEDIA-001:** Every media record MUST receive an application-generated UUIDv7.
- **MEDIA-002:** Every imported file MUST receive a SHA-256 hash over its original bytes.
- **MEDIA-003:** Exact SHA-256 duplicates MUST resolve to one media record and one evaluation history.
- **MEDIA-004:** Multiple source locations for the same exact file MUST be retained as separate source references.
- **MEDIA-005:** Original filename and path MUST NOT be used as unique identifiers.
- **MEDIA-006:** Same-name files with different bytes MUST become different media records.
- **MEDIA-007:** Original managed media bytes MUST be immutable.
- **MEDIA-008:** Source disappearance MUST NOT delete the managed copy.
- **MEDIA-009:** Evaluation Trash MUST NOT physically delete media.

## Import and processing

- **ING-001:** The MVP MUST support authenticated browser uploads.
- **ING-002:** The MVP MUST support configured NAS import roots with manually triggered rescans.
- **ING-003:** An import root MUST NOT overlap managed storage.
- **ING-004:** Source inventory MUST track root, relative path, size, modification time, SHA-256, last-seen scan, status, error, and linked media.
- **ING-005:** Rescans SHOULD skip unchanged path/size/mtime entries before hashing.
- **ING-006:** Renames or moves detected by SHA-256 MUST link to the existing media record.
- **ING-007:** Changed bytes at an existing source path MUST create a new immutable media record.
- **ING-008:** Processing MUST be asynchronous, stage-based, durable, retryable, and observable.
- **ING-009:** A failed extraction or enrichment stage MUST NOT discard the original file.
- **ING-010:** One failed item MUST NOT block the remainder of a batch.
- **ING-011:** The MVP MUST support PNG, JPEG, WebP, MP4, and WebM.
- **ING-012:** Container and codec MUST be stored separately.
- **ING-013:** Browser-incompatible video MUST retain its original and MAY receive an H.264 MP4 proxy.
- **ING-014:** The UI MUST distinguish proxies from originals and permit original download.
- **ING-015:** Import progress MUST survive API or worker restarts.
- **ING-016:** Authenticated machine clients MUST be able to submit media through
  the same durable multipart import and processing pipeline used by browser uploads.

## Workflow ground truth and graph

- **WF-001:** Complete embedded prompt/workflow metadata MUST be stored unchanged.
- **WF-002:** Reprocessing MUST never alter embedded ground truth.
- **WF-003:** Every parseable node, typed value, connection, and node property MUST be preserved in a generic graph representation.
- **WF-004:** Embedded API-prompt and visual-workflow forms MUST be stored independently when both exist.
- **WF-005:** Malformed or partial workflow data MUST produce a parse status and error without failing media import.
- **WF-006:** Semantic extraction MUST be versioned.
- **WF-007:** Every semantic observation MUST retain source, extractor version, confidence, and correction state.
- **WF-008:** Unknown nodes and values MUST remain inspectable.
- **WF-009:** Prompt text MUST be stored and displayed without semantic sanitization, redaction, or rewriting.
- **WF-010:** Untrusted prompt content MUST be rendered as text and never executed as HTML.
- **WF-011:** Prompt roles MUST be correctable independently from prompt text. Explicit
  mappings MUST take precedence over graph inference; positive/main prompts MUST be
  presented before unclassified and negative prompts without discarding any role.

## Offline node registry

- **NODE-001:** The application MUST maintain a persistent node-definition registry.
- **NODE-002:** ComfyUI `/object_info` snapshots MAY enrich that registry but MUST NOT be required during ordinary import.
- **NODE-003:** ComfyUI installations MUST NOT be modeled as persistent application entities.
- **NODE-004:** Node-definition variants MUST be keyed by class/module/schema fingerprint rather than class name alone.
- **NODE-005:** First-run classification MUST be performed automatically using built-in knowledge, schemas, graph types, model-list matches, names, values, and repeated evidence.
- **NODE-006:** High-confidence inferred tags MAY become active automatically and MUST remain visibly inferred.
- **NODE-007:** Ambiguous suggestions MUST NOT affect analytical factors until accepted.
- **NODE-008:** Manual corrections MUST override automated inference.
- **NODE-009:** A correction MUST be able to trigger reprocessing of every affected workflow.
- **NODE-010:** The MVP MUST provide an unknown-node inbox and persistent manual input mappings.
- **NODE-011:** A full visual rule-authoring system is deferred.
- **NODE-012:** A LoRA mapping whose located value is a structured collection MUST
  create one current semantic observation for each explicitly active entry, MUST
  exclude explicitly inactive entries from current model usage, and MUST preserve
  the complete collection in embedded ground truth.

## Model registry

- **MODEL-001:** Canonical model artifacts SHOULD use hashes when available.
- **MODEL-002:** Model type, filenames, aliases, hashes, architecture family, lineage, precision, quantization, training series, and enrichment provenance MUST be independently representable.
- **MODEL-003:** Model availability, identity confidence, and Civitai enrichment status MUST be separate axes.
- **MODEL-004:** Absence from Civitai MUST NOT make a locally known model unresolved.
- **MODEL-005:** Workflow-only deleted models MUST remain as historical references.
- **MODEL-006:** Historical references MUST participate in analysis under exact embedded identity, with visible provenance.
- **MODEL-007:** An unambiguous filename-only match MAY create a reversible inferred canonical link.
- **MODEL-008:** Multiple filename matches MUST remain ambiguous.
- **MODEL-009:** LoRA Manager MUST be the primary live source for checkpoint and LoRA inventory.
- **MODEL-010:** LoRA Manager scan, Civitai fetch, and registry import MUST report independent stage outcomes.
- **MODEL-011:** Civitai misses or network failures MUST produce partial success rather than aborting synchronization.
- **MODEL-012:** Model usage MUST be one-to-many per workflow and retain pipeline pattern and usage slot.
- **MODEL-013:** Canonical artifact identity MUST remain independent of its workflow usage role.
- **MODEL-014:** Architecture family and pipeline pattern SHOULD form default analytical boundaries.
- **MODEL-015:** Raw workflow model-reference values MUST remain unchanged when path-qualified
  and basename-only aliases are grouped as one analytical identity.
- **MODEL-016:** References linked to the same canonical artifact MAY be grouped automatically;
  basename-only matches without shared artifact evidence MUST require confirmation, and
  references linked to different artifacts MUST NOT be grouped.
- **MODEL-017:** Confirmed reference-alias groups MUST be reversible and MUST be honored by
  library/review filters and model analytics without reprocessing media or evaluations.

## Locally trained LoRA series

- **LORA-001:** Locally trained adapters with a final numeric filename suffix MUST be representable as a training series.
- **LORA-002:** Only the final numeric suffix is interpreted as the step count; the preceding text remains opaque.
- **LORA-003:** Leading zeroes in the numeric suffix MUST be removed when converting to an integer.
- **LORA-004:** Series inference MUST remain correctable through merge, split, and step edits.
- **LORA-005:** Missing historical series members MUST remain analyzable.

## Library organization

- **LIB-001:** The library MUST support source-folder filtering.
- **LIB-002:** The library MUST support static collections without copying media.
- **LIB-003:** The library MUST support reusable dynamic saved filters.
- **LIB-004:** The library MUST support manual tags.
- **LIB-005:** Large galleries MUST use pagination or virtualization rather than rendering every item.
- **LIB-006:** Import, processing, parsing, and registry errors MUST be visible and filterable.
- **LIB-007:** The library MUST support deterministic sorting by file time, import
  time, filename, and byte size, with newest file time as the default.
- **LIB-008:** Media Detail MUST provide Previous and Next traversal over the exact
  filtered and sorted library context from which it was opened, including across
  pagination boundaries.
- **LIB-009:** The library and reusable filter scopes MUST support checkpoint and
  LoRA-reference identity filters, including historical workflow-only references and
  confirmed aliases.
- **LIB-010:** The gallery grid MUST default to a 2:3 portrait preview frame and use
  responsive card sizing that keeps common portrait generations comfortably
  inspectable on a laptop display.
- **LIB-011:** Library selection MUST support the current page and the complete
  server-filtered result set without transferring every matching media UUID to the
  browser; filtered scopes MUST be usable for review, collections, and tags.
- **LIB-012:** Checkpoint and LoRA filters MUST accept multiple identities with an
  explicit Any (OR) or All (AND) mode. Any MUST be the default within each model
  dimension, while different filter dimensions remain combined with AND.
- **LIB-013:** Desktop navigation MUST collapse into a persistent icon rail without
  removing route labels from accessible names; compact-screen navigation MUST remain
  usable independently of the saved desktop preference.
- **LIB-014:** Media Detail and Blind Review MUST use a viewport-height media stage
  beside an independently scrollable inspector. Media Detail MUST prioritize filename,
  exact prompts, and checkpoint/LoRA usages, while basic file facts, UUID, and SHA-256
  remain available as compact secondary evidence. Media MUST be contained inside
  the current dynamic viewport without control overlays or edge clipping. Blind Review
  MUST preserve its configuration-hiding invariant.

## Manual evaluation

- **EVAL-001:** Evaluation MUST be manual in the MVP.
- **EVAL-002:** Applicable criteria MUST come from a versioned template snapshot.
- **EVAL-003:** Image/video core selection MUST follow media type.
- **EVAL-004:** Optional modules MUST be explicitly assigned to a review session or
  enabled for an individual media record.
- **EVAL-005:** Later criteria additions MUST NOT reopen or invalidate completed historical evaluations.
- **EVAL-006:** Every criterion value MUST be either unset, N/A, or an integer from 0 through 10.
- **EVAL-007:** Zero MUST remain a real score distinct from unset and N/A.
- **EVAL-008:** N/A MUST count as resolved for completion and MUST be excluded from numerical summaries.
- **EVAL-009:** Evaluation state MUST derive as Not started, In progress, or Complete.
- **EVAL-010:** Trash MUST be a separate reversible state.
- **EVAL-011:** Trash MUST preserve existing scores but exclude them by default from analysis.
- **EVAL-012:** Marking Trash MUST NOT automatically navigate to another media item.
- **EVAL-013:** Completing a media MUST NOT automatically navigate.
- **EVAL-014:** Partial scores MUST autosave and appear in a global In progress pool.
- **EVAL-015:** Completed evaluations MUST remain editable.
- **EVAL-016:** Score edits MUST retain revision history.
- **EVAL-017:** Review MUST hide checkpoint, LoRA, workflow configuration, and other experiment-revealing metadata.
- **EVAL-018:** Review MUST show exact extracted prompt fields.
- **EVAL-019:** A review session MUST be resumable but MUST NOT impose completion, deadlines, or streak behavior.
- **EVAL-020:** Media Detail MUST expose an Info/Evaluate panel switch beside the
  filename and preserve the selected panel while navigating Previous/Next.
- **EVAL-021:** Media Detail evaluation MUST use the same templates, scores,
  autosave, revision history, and Trash disposition as Blind Review while keeping
  workflow and model evidence visible.
- **EVAL-022:** Optional evaluation-module selection MUST be stored per media.
  Disabling a module MUST hide it from the active evaluation and completion state
  without deleting any scores; re-enabling it MUST restore the saved evaluation.

## Analytics

- **AN-001:** Only Complete evaluations MAY enter analysis by default.
- **AN-002:** Trash MUST be excluded by default and available only through explicit inclusion.
- **AN-003:** Analysis MUST be observational and describe association or tendency rather than causality.
- **AN-004:** Prompts MUST NOT be used for default matching or balancing.
- **AN-005:** Filters selected by the user define the population being described.
- **AN-006:** MVP reports MUST cover checkpoint profiles, checkpoint-pair profiles, LoRA profiles, LoRA training-step trends, checkpoint-by-LoRA matrices, and exact LoRA-combination profiles.
- **AN-007:** Sampling settings, prompts, seeds, dimensions, and LoRA strengths MUST remain filterable metadata but need no dedicated MVP reports.
- **AN-008:** Reports MUST show sample count, coverage, mean, median, distribution, interquartile range, uncertainty, effect size, Trash count, and N/A count where applicable.
- **AN-009:** Reports MUST NOT reduce conclusions to a simple winner declaration.
- **AN-010:** A saved analysis MUST snapshot the exact media, score revisions, filters, grouping, exclusions, template, and weighting profile used.
- **AN-011:** Saved analyses MUST remain immutable; rerunning creates a new version.
- **AN-012:** Criterion scores MUST remain raw source data; composite scores MUST be calculated by versioned weighting profiles.
- **AN-013:** Equal weighting MUST be the default profile.
- **AN-014:** Overall comparisons across template versions MUST use shared criteria by default and show coverage.

## Operations and recovery

- **OPS-001:** The MVP MUST run under Docker Compose on x86 Linux.
- **OPS-002:** The API and background worker MUST be separate services.
- **OPS-003:** PostgreSQL MUST be the authoritative metadata store.
- **OPS-004:** Redis with Dramatiq MUST transport background work.
- **OPS-005:** Media and generated derivatives MUST live on mounted filesystem volumes, not in PostgreSQL.
- **OPS-006:** Python environments and dependencies MUST be managed with `uv`.
- **OPS-007:** Automatic PostgreSQL backups MUST support configurable daily and weekly retention.
- **OPS-008:** Restore procedures MUST be documented and tested.
- **OPS-009:** Evaluations, criteria, registry, and analysis data MUST support portable export.
- **OPS-010:** Schema changes MUST use Alembic migrations.
- **OPS-011:** Heavy background concurrency MUST be bounded for the J4125 CPU.
- **OPS-012:** Ordinary development MUST run against isolated Mac-local database,
  broker, managed storage, and credentials rather than NAS production state.
- **OPS-013:** Production milestone images MUST be built for `linux/amd64` by CI,
  tagged immutably by locked version, and pulled by the NAS without compilation.
- **OPS-014:** The milestone deployment command MUST require a fresh backup,
  migration/drift preflight, explicit version confirmation, and post-start health
  verification.
