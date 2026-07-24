# MVP Scope

**Status:** Accepted

## MVP objective

Deliver a dependable local application that can import an existing ComfyUI media library, preserve and interpret its workflow metadata, support interruption-friendly manual evaluation, and analyze checkpoint/LoRA tendencies.

## Included capabilities

### Foundation

- Docker Compose deployment for x86 NAS.
- FastAPI backend, separate Dramatiq worker, PostgreSQL, Redis, and React/TypeScript frontend.
- Single administrator login and revocable API tokens.
- Alembic migrations, structured configuration, health checks, and backup tooling.

### Media library

- Authenticated browser import.
- Configured NAS source roots and manual rescans.
- Durable source inventory and processing jobs.
- Immutable managed originals, exact SHA-256 deduplication, UUIDv7 record identity.
- Image thumbnails, video inspection, and browser-compatible proxies when necessary.
- Virtualized gallery/table, static collections, saved filters, tags, source provenance, and error views.

### Workflow intelligence

- Extraction of embedded prompt and workflow data from supported media.
- Immutable raw metadata, generic nodes/edges, and versioned semantic features.
- Offline node schema and semantic registry.
- Optional on-demand ComfyUI schema synchronization.
- Automatic high-confidence classification and unknown-node review inbox.
- Manual input tagging for checkpoint, LoRA, prompt, and supported configuration classes.

### Model registry

- LoRA Manager synchronization for LoRAs and checkpoints.
- Raw provider response caching and stage-level synchronization results.
- Hash identity when available, filename-based inferred identity when necessary.
- Historical workflow-only model references.
- Architecture, lineage, pipeline pattern, usage slot, and checkpoint-pair representation.
- Local LoRA training-series detection and correction.

### Evaluation

- Versioned core, video, and character rubrics.
- Configuration-blind, prompt-aware review screen.
- Nullable integer sliders, N/A, clear, autosave, keyboard actions, anchors, and undo.
- Not started, In progress, Complete, and reversible Trash states.
- Static review-session snapshots and global In progress resumption.
- Editable completed scores with revision history.

### Analytics

- Live exploratory filters.
- Immutable saved analysis runs.
- Checkpoint, checkpoint-pair, LoRA, training-step, checkpoint-by-LoRA, and LoRA-combination reports.
- Descriptive statistics, distributions, uncertainty, effect sizes, coverage, and evidence-strength language.
- Versioned composite weighting profiles with equal-weight default.

## Explicit non-goals

The following are **Deferred** and MUST NOT be introduced into the MVP accidentally:

- Automated image/video benchmark scoring.
- CUDA or other GPU workers.
- Perceptual-hash deduplication or visual-similarity search.
- Strict prompt-controlled or causal model comparisons.
- Dedicated LoRA-strength or sampler-recipe reports.
- Full arbitrary visual parser-rule authoring.
- Multi-user accounts, permissions, or collaboration.
- Persistent ComfyUI instance management.
- Automatic Hugging Face model enrichment.
- A ComfyUI custom node that uploads media directly.
- A ComfyUI custom node that retrieves saved workflows/configurations.
- Physical media purge workflows.

## Post-MVP candidates

### Integration and analysis extensions

- ComfyUI custom save/upload node using the implemented generic ingestion endpoint.
- Media/workflow retrieval API for ComfyUI custom nodes.
- Hugging Face enrichment provider.
- Declarative parser rule editor with impact preview.
- Visual-similarity search based on embeddings.
- Richer model interaction and sensitivity analysis.

### Longer-term platform extensions

- Optional automated evaluation providers on external hardware.
- Multi-user review and inter-rater analysis.
- External object storage.
- Cross-library federation.

## MVP definition of done

The MVP is done only when:

1. A representative bulk import can restart safely after interruption.
2. Original files and raw metadata are demonstrably preserved.
3. Known and unknown workflows remain browsable.
4. Model/node corrections reprocess affected media without corrupting ground truth.
5. Review can stop and resume across days without score loss.
6. All locked criteria and state transitions are tested.
7. Every accepted analytical report works on completed media and records its dataset snapshot.
8. Backup restoration recovers users, registry, evaluations, and analyses.
9. The golden image/video corpus passes extraction regression tests.
10. Deployment remains usable within J4125 resource constraints.
