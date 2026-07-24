# Phase 3 Node and Model Registries

**Status:** Implemented and verified
**Migration head:** `0004_node_model_registries`
**Target runtime:** Local-network Linux AMD64 Docker host without CUDA

## Delivered outcome

Phase 3 turns the immutable workflow evidence from Phase 2 into correctable,
offline-capable node and model identities. A live ComfyUI installation is useful for
synchronization, but is not required for import, browsing, reprocessing, or querying
previously synchronized registry data.

The phase delivers:

1. Versioned ComfyUI `/object_info` snapshots and normalized node definitions.
2. Automatic semantic input mappings with explicit confidence and provenance.
3. Compatibility matching for current and historical workflow nodes.
4. LoRA Manager-backed checkpoint and LoRA inventory synchronization.
5. Canonical, ambiguous, unresolved, and workflow-only historical model references.
6. Per-workflow model usages with pipeline pattern and usage slot.
7. Correctable local LoRA training series.
8. User-defined checkpoint comparison groups for later observational analysis.

The immutable media and embedded workflow remain ground truth. Registry records are
versioned or correctable overlays; they never rewrite the source evidence.

## Live integration audit

The implementation was verified against the user's running ComfyUI and installed
LoRA Manager, not only against synthetic fixtures.

Observed source contract:

- ComfyUI version: `0.27.1`.
- `/object_info`: 4,360 node definitions, approximately 10 MiB.
- LoRA Manager inventory: 391 LoRAs and 28 checkpoints.
- Golden corpus: 6 PNG images and 8 MP4 videos.
- LoRA Manager local scan and bulk Civitai-fetch commands returned stage responses.

The live synchronization result contained:

- 4,360 current node definitions.
- 2,444 automatically inferred semantic mappings.
- 677 exact/compatible workflow-node matches.
- 45 historical workflow-node matches.
- 14 retained historical node-definition variants.
- 419 present model artifacts.
- 415 hash-verified artifacts.
- 289 provider-enriched artifacts.
- 24 resolved workflow model references.
- 4 workflow-only historical model references.
- 55 per-workflow model usages.
- 2 detected local LoRA training series.

These counts describe the validation environment and are not application constants.

## Persistence

Migration `0004_node_model_registries` adds:

| Table | Purpose |
|---|---|
| `registry_sync_run` | Durable synchronization request, stage outcomes, counts, source versions, and errors |
| `node_schema_snapshot` | Raw immutable `/object_info` payload and content hash |
| `node_definition` | Normalized class/module/schema-fingerprint variant |
| `node_semantic_mapping` | Correctable input/widget semantic locator |
| `model_artifact` | Current canonical checkpoint/LoRA/file identity |
| `model_reference` | Exact workflow-embedded model reference and its resolution state |
| `model_usage` | Artifact/reference occurrence in one workflow pipeline and slot |
| `lora_series` | Opaque local training-run identity |
| `lora_series_member` | Model reference, integer training step, and correction state |
| `comparison_group` | User-owned analysis boundary |
| `comparison_group_member` | Canonical artifact selected for a comparison group |

`workflow_node` gains a nullable definition link, match state, and confidence. Existing
workflow evidence and semantic observations remain intact.

## Durable synchronization

Registry work runs on the separate Dramatiq worker and records every stage in
PostgreSQL. Redis transports work but is never the authoritative status store.

### Node synchronization

Required stages:

1. Fetch system/version information, feature flags, and `/object_info`.
2. Validate the response and enforce the configured definition/response limits.
3. Hash and persist the raw snapshot.
4. Normalize and fingerprint every definition variant.
5. Create first-pass semantic mappings.
6. Resolve imported workflow nodes against current and historical definitions.
7. Reprocess affected workflow semantics.

A required-stage failure marks the run and job failed with a stable error code. An
unexpected adapter exception is converted to a safe structured failure rather than
leaking a stack trace to the client.

### Model synchronization

Stages:

1. Optionally request LoRA and checkpoint local scans.
2. Optionally request bulk Civitai enrichment.
3. Fetch LoRA Manager LoRA/checkpoint inventories and ComfyUI model-folder lists.
4. Fetch bounded per-file metadata with low concurrency.
5. Import and reconcile canonical artifacts.
6. Resolve workflow references.
7. Replace current workflow model usages and update LoRA series.

Local inventory import is required. Scan, provider enrichment, and individual metadata
failures are optional stages: they produce `partial` rather than discarding usable
local data.

## Node-definition identity and matching

A definition variant is uniquely identified by:

```text
class_type + python_module + canonical_schema_fingerprint
```

The fingerprint is derived from normalized input/output structure rather than display
text. This prevents a newly installed custom-node version from silently overwriting a
historical schema with the same class name.

Workflow-node resolution prefers:

1. Exact current class/module/schema compatibility.
2. Compatible current variants using input and widget structure.
3. A persisted historical definition synthesized from embedded workflow evidence.
4. Ambiguous or unresolved state when no safe match exists.

Unknown nodes remain queryable and filterable. The Node Registry page provides an
unknown filter, definition detail, raw schema on demand, mapping evidence, and a
persistent manual input-mapping editor.

Manual mappings use the highest precedence. Saving one queues workflow reprocessing;
older extraction runs and raw evidence remain unchanged.

Release `0.1.0-rc.5` extends a manual `lora_reference` mapping to structured loader
collections. The extractor emits one observation/model usage for every explicitly
active named entry, ignores inactive entries as current usages, and preserves
collection index and strength evidence. It intentionally keys this behavior by
semantic type and value shape instead of one node title or schema fingerprint.

## Automatic semantic mapping

The first run maps supported meanings from schema and graph evidence:

- Checkpoint reference.
- LoRA reference.
- Prompt.
- Generation/sampler parameter.

Every mapping retains:

- Stable locator kind and locator value.
- Semantic type and optional role.
- Source (`automatic` or `manual`).
- Confidence.
- Activation/correction state.
- Evidence used for inference.

Ambiguous candidates do not become analytical factors. Manual correction remains
authoritative across later synchronization and reprocessing.

## Model identity

The registry deliberately separates:

- The canonical artifact currently known to LoRA Manager.
- The exact path/name embedded in a workflow.
- Artifact availability.
- Identity/match confidence.
- Civitai enrichment state.
- Architecture family and model lineage.
- Precision and quantization.
- The artifact's usage role in a particular workflow.

Hashes are preferred when supplied. Normalized full paths and basenames are indexed
as aliases, but a filename match is accepted only when unambiguous. Multiple candidates
remain visible and unresolved. A user can manually link or unlink a reference.

A reference absent from current inventory is retained as `historical` with the exact
embedded value and `missing` availability. It remains usable for counts and later
analysis even when neither the file nor Civitai metadata exists.

Provider metadata never overwrites a manually corrected artifact field.

## Pipeline patterns and usage slots

Model role belongs to a workflow occurrence, not to the canonical artifact.

Implemented patterns and slots:

| Pipeline pattern | Checkpoint slots |
|---|---|
| `single_model` | `single` |
| `dual_noise` | `high_noise`, `low_noise` |
| `single_pass` | `single` |
| `dual_pass` | `first_pass`, `second_pass` |
| `unclassified` | `unclassified` |

LoRAs are retained as separate `adapter` usages in the same pipeline. Graph traversal,
sampler relationships, and conservative Wan/Krea architecture hints provide the
classification evidence.

The golden corpus verified all four classified patterns. In particular, the Krea 2
Raw checkpoint used for the first pass and the Turbo-lineage checkpoint used for the
second pass appeared as separate usages without creating duplicate artifact identities.

Architecture family plus pipeline pattern is the default future analysis boundary.
Comparison groups let the user explicitly decide which compatible artifacts may
compete within that boundary.

## Local LoRA training series

Only an exact trailing underscore and numeric filename component is interpreted:

```text
Krea2_guzong_lora_v2_000003500.safetensors
```

becomes:

```text
opaque_name = Krea2_guzong_lora_v2
training_step = 3500
```

Everything before the final underscore is opaque. Leading zeroes affect neither the
integer step nor the preserved raw filename.

The user can:

- Rename a series display name.
- Correct an individual step.
- Merge one or more inferred series into a target.
- Split selected members into a new opaque series.

Merge, split, and step edits mark the member assignment as corrected. Automatic
re-resolution skips manually assigned references, so it cannot recreate an obsolete
filename-derived series after a correction. Missing historical references can be
series members.

## API surface

Implemented authenticated endpoints:

```text
POST  /api/v1/node-registry/sync
POST  /api/v1/model-registry/sync
GET   /api/v1/registry-sync-runs

GET   /api/v1/node-definitions
GET   /api/v1/node-definitions/:id
POST  /api/v1/node-mappings

GET   /api/v1/models
GET   /api/v1/models/:id
PATCH /api/v1/models/:id
GET   /api/v1/model-references
POST  /api/v1/model-references/:id/link

GET   /api/v1/lora-series
PATCH /api/v1/lora-series/:id
PATCH /api/v1/lora-series-members/:id
POST  /api/v1/lora-series/:id/merge
POST  /api/v1/lora-series/:id/split

GET   /api/v1/comparison-groups
POST  /api/v1/comparison-groups
PATCH /api/v1/comparison-groups/:id
```

Model-usage roles are included in the media workflow response. Registry queries use
bounded pagination and load large raw definitions only for explicit detail requests.
Cookie-authenticated mutations require CSRF; API tokens can perform the same
authenticated calls.

MVP registry corrections use single-user last-write-wins behavior. Multi-user
optimistic correction preconditions remain deferred with RBAC.

## Frontend

The route-split React application adds:

- Node Registry navigation and page.
- Model Registry navigation and page.
- Durable synchronization history with active-run polling.
- Node search, status/source filtering, bounded pagination, and unknown-node view.
- Definition/schema/mapping detail and manual mapping editor.
- Artifact search/filter/detail and manual identity-field corrections.
- Workflow-reference search and manual canonical links.
- LoRA series rename, step edit, merge, and split controls.
- Comparison-group creation and editing.
- Workflow inspector model-usage pattern/slot and node-definition match state.

Large registry lists use pagination and deferred rendering. Raw definition JSON is
not loaded into the initial list response.

## Offline and failure behavior

The implementation was explicitly tested with an unreachable ComfyUI URL:

- The sync run failed with `COMFYUI_UNAVAILABLE`.
- The previously cached 4,360 node definitions remained queryable.
- Existing media, workflow, model-reference, and manual-correction views remained
  usable.

The application does not store or manage ComfyUI instance entities. A URL is
per-request or server configuration only. Ordinary import and registry queries make
no request to ComfyUI.

## Migration verification

The migration was validated in two directions:

1. A clean PostgreSQL database upgraded from no schema to head and passed Alembic
   drift checking.
2. An isolated database upgraded from `0003_workflow_evidence` to
   `0004_node_model_registries`; a pre-existing administrator row remained intact and
   Alembic reported no pending schema operations.

No migration performs network access or requires ComfyUI.

## Verification

Automated verification covers:

- Node-schema hashing, fingerprints, and input classification.
- Registry URL validation and bounded external responses.
- Model inventory import before server defaults are flushed.
- Strong Wan 2.1/Wan 2.2/Krea 2 architecture and lineage hints.
- Historical node/model preservation.
- Dual-noise and dual-pass graph role classification.
- Exact LoRA suffix parsing and leading-zero removal.
- Manual LoRA merge/split durability across automatic re-resolution.
- Existing media ingestion, evidence, authentication, and worker regressions.
- Ruff, format, strict mypy, pytest, ESLint, TypeScript, Vitest, and Vite production
  build.

Live Docker/API/browser verification covers:

- Full node and model synchronization.
- Import and parsing of all 14 private golden files.
- Manual node mapping followed by queued reprocessing.
- Manual artifact correction and reference link.
- Comparison-group creation.
- LoRA step editing, merge, split, and restored series membership.
- Krea dual-pass usage display in the workflow inspector.
- Cached registry access with the external source unavailable.
- Explicit Linux AMD64 backend and web image builds.

## Phase boundary

Phase 3 does not implement scoring, blind review, experiment execution, or statistical
reports. It supplies the stable model/node factors and correction controls those
features require.

Phase 4 begins with versioned manual evaluation criteria, nullable integer sliders,
Trash behavior, resumable review sessions, and the blind media-first review page.
