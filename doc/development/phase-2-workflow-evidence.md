# Phase 2 Workflow Evidence and Parser Verification

**Status:** Implemented and verified
**Migration head:** `0003_workflow_evidence`
**Target runtime:** Local-network Linux AMD64 Docker host without CUDA

## Delivered outcome

Phase 2 turns every supported media original into an optional, immutable ComfyUI
evidence record and a versioned interpretation. Media without metadata remains valid;
malformed metadata remains preserved; unknown custom nodes remain inspectable.

This phase implements the first three layers of the accepted workflow-intelligence
design:

1. Exact decoded carrier evidence.
2. A registry-independent generic graph.
3. Conservative built-in semantic observations.

Evaluation and analysis remain later phases.

## Golden corpus audit

The user supplied 14 private originals:

- 6 PNG images.
- 8 MP4 videos.
- 11 distinct API graph signatures.
- 13 files with both API prompt and visual workflow.
- 1 valid API-prompt-only video.

The corpus covers:

- Krea 2 single-pass and Raw-to-Turbo dual-pass graphs.
- Wan 2.1 single-model graphs.
- Wan 2.2 high/low-noise graphs.
- Safetensors and GGUF model loaders.
- Core and custom LoRA loaders, including LoRA Manager nodes.
- A local training-step LoRA filename.
- Large custom-node graphs and nodes unknown to the built-in extractor.
- VHS video output metadata stored in the MP4 format comment.

Private originals were moved from `incoming/` into hash-derived case directories such
as `image-<sha-prefix>/original.png`. Original filenames are not case identities.
All originals and local expectation files remain ignored by Git.

## Evidence readers

The reader is selected from content detection, never from the filename:

| Media carrier | Evidence source |
|---|---|
| PNG | Text chunks and image metadata |
| JPEG/WebP | Image metadata and EXIF, including `UserComment` wrappers |
| MP4/WebM | `ffprobe` format tags, including `comment`/`COMMENT` wrappers |

The reader:

- Preserves the carrier metadata as JSON-compatible raw evidence.
- Preserves exact prompt/workflow strings when the carrier exposes them as strings.
- Stores API prompt and visual workflow independently.
- Handles JSON nested as a string inside a wrapper.
- Assigns a SHA-256 integrity hash to the decoded carrier evidence.
- Applies configurable byte, nesting, item, and node limits before normalization.

The immutable media file remains the ultimate byte-level ground truth. For MP4/WebM,
`ffprobe` supplies decoded container tags; the complete decoded comment is retained
even when its child prompt/workflow objects require normalization.

## Workflow state model

Representation states:

- `absent`
- `parsed`
- `malformed`

Overall workflow states:

- `unprocessed` — no snapshot exists yet.
- `absent` — the carrier contains neither supported representation.
- `parsed` — at least one representation parsed and none was malformed.
- `partial` — one representation parsed while another candidate was malformed.
- `malformed` — metadata candidates exist but none can be parsed.
- `failed` — the carrier metadata reader itself failed.

A valid prompt-only or visual-only file is `parsed`, not `partial`. `partial` means
damage or invalid structure, not merely that a representation was never embedded.

## Persistence

Migration `0003_workflow_evidence` adds:

| Table | Purpose |
|---|---|
| `workflow_snapshot` | One immutable evidence snapshot per exact media identity |
| `workflow_node` | API and visual nodes with original IDs and raw fields |
| `workflow_edge` | API input links and visual workflow links |
| `workflow_value` | Named API values and position-only visual widgets |
| `extraction_run` | Version, configuration hash, reason, status, and current marker |
| `semantic_observation` | Typed value, confidence, and source evidence |

Raw evidence is never updated during parser reprocessing. Generic graph records may
be regenerated when the graph normalizer version changes. Older semantic observations
remain attached to their extraction run; their node foreign key safely becomes null
if a future graph version replaces node records, while their evidence JSON retains the
original representation and node ID.

## Generic graph normalization

API prompt normalization stores:

- Every node ID and `class_type`.
- Named inputs and constants.
- Links represented as `[source_node_id, output_index]`.
- Titles and API metadata.

Visual workflow normalization stores:

- Every node ID, type, title, mode, properties, inputs, and `widgets_values`.
- Every global link with source/destination slots and declared type.
- Widget values with stable position locators even when no node definition exists.

No current ComfyUI API or node package is required. Unknown nodes are ordinary graph
records rather than parser failures.

## Built-in semantic extraction

The Phase 2 extractor intentionally uses only high-confidence named API inputs:

- `ckpt_name`, `unet_name`, and supported primary-loader `model_name` values become
  `checkpoint_reference` observations.
- `lora_name` becomes a `lora_reference` observation.
- Known prompt-bearing named inputs become `prompt` observations.
- Seed, steps, CFG, sampler, scheduler, denoise, width, and height become
  `generation_parameter` observations.

Each observation records confidence, representation, node ID, class, input name,
extraction method, and the initial correction state `uncorrected`. Checkpoint pipeline
slots, architecture families, canonical model identity, and LoRA training-series
grouping remain Phase 3 work. Phase 2 therefore uses the explicit role `unclassified`
rather than guessing.

## Durable pipeline integration

New imports run these durable stages:

1. Hash and validate.
2. Store immutable original.
3. Probe media.
4. Extract workflow.
5. Generate derivatives.

Workflow absence is success. Malformed metadata creates a warning but does not block
thumbnail/poster generation or media readiness. A reader/extractor crash records a
failed snapshot/run and stage error while the media continues as
`ready_with_warnings`.

Existing Phase 1 media can be processed through:

- Per-media reprocessing.
- Bulk `missing` backfill.
- A duplicate import that encounters a ready media identity without a snapshot.

The Dramatiq worker remains bounded to one process and one thread on the target NAS.
Its async actors use Dramatiq's process-scoped event-loop middleware, so SQLAlchemy
and `asyncpg` connections are never reused across short-lived event loops.

## API surface

Implemented endpoints:

```text
GET  /api/v1/media/:id/workflow
GET  /api/v1/media/:id/workflow/raw
POST /api/v1/media/:id/workflow/reprocess
POST /api/v1/workflows/reprocess
```

Media list/detail responses expose `workflow_status`; list filtering accepts
`workflow_status`.

The summary/graph endpoint applies bounded node and edge limits. Raw metadata and full
decoded workflows are returned only by the explicit raw endpoint, never by gallery
list responses.

## Frontend

The media library provides a workflow-status filter and status badge. Media detail
provides:

- API/visual representation states and node counts.
- Evidence reader version and evidence hash.
- Checkpoint, LoRA, prompt, and generation-parameter observations.
- Prompt text rendered plainly as text.
- Representation and node search.
- Lazily expanded node inputs, widget values, and properties.
- Lazily expanded edge inspection.
- Raw evidence fetched and rendered only after an explicit action.
- Extraction-run history and background reprocessing.

The Imports page provides a bulk “Process unparsed media” command for upgrades.

The workflow inspector remains part of the already route-split Media Detail bundle.
Large node rows use deferred detail rendering and CSS content visibility.

## Verification

Automated verification:

- Ruff lint and format checks.
- Strict mypy.
- 22 Python tests.
- 4 frontend tests.
- ESLint and TypeScript project build.
- Vite production build.

The Python suite covers:

- Exact PNG prompt/workflow text preservation.
- JPEG/WebP EXIF wrappers.
- MP4 private corpus comment wrappers.
- Synthetic WebM format tags.
- Prompt-only, absent, and partially malformed states.
- Unknown nodes.
- API and visual graph normalization.
- Checkpoint/LoRA/prompt observations.
- Media readiness after malformed metadata.
- Multiple extraction runs with exactly one current run.
- An unchanged evidence hash after reprocessing.

Fresh Docker/PostgreSQL verification demonstrated:

- Migration upgrade to `0003_workflow_evidence`.
- Alembic schema-drift check with no pending operations.
- Read-only scan of all 14 private originals.
- 14 imports, zero failures.
- 14 parsed workflow snapshots.
- Successful raw-evidence retrieval without including raw workflow data in list calls.
- Successful background reprocessing.
- A second extraction run with the same evidence hash.
- A full 14-media queued reprocessing batch with zero failures, clean worker logs,
  and exactly 14 current extraction runs.
- `missing` backfill returning zero after the corpus completed.
- Workflow-status filtering.

Browser verification demonstrated:

- Workflow badges and filters across the 14-card gallery.
- Plain prompt rendering.
- Checkpoint and LoRA observations.
- Node search reducing a 67-node combined graph to four matching nodes.
- On-demand node payload expansion.
- On-demand raw evidence loading.
- Correct UI treatment of the prompt-only video as API `Parsed`, visual `Absent`.
- Successful video playback with browser `readyState = 4`.

## Phase boundary

Phase 2 does not implement:

- Live ComfyUI `/object_info` sync.
- Offline node-definition variants or fingerprints.
- User corrections and affected-workflow reprocessing.
- LoRA Manager synchronization.
- Canonical/historical model identity.
- Pipeline-pattern and checkpoint-slot classification.
- Local LoRA training-series grouping.

Those capabilities form Phase 3.
