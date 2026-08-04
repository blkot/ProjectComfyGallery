# Requirements Traceability

**Status:** Active governance document
**Current implementation state:** MVP Phases 0 through 6 implemented and verified

## Purpose

This matrix connects product requirements to design, delivery phase, and expected verification. During implementation, code/module and test references must be added rather than replacing the requirement IDs.

## Capability matrix

| Requirement IDs | Capability | Governing design | Planned phase | Primary verification | Status |
|---|---|---|---|---|---|
| AUTH-001–004 | Single-user login, session, revocable tokens | [API](interfaces/api-and-integrations.md), [Security](operations/deployment-and-security.md), [ADR-0009](decisions/0009-single-user-authentication.md) | 0, 6 | `comfy_gallery_core.auth/security`, API auth routes, `test_auth_store.py`, browser/API contract check | Locked in 0.1.0-rc.6 |
| MEDIA-001–008 | UUIDv7 identity, SHA-256 exact deduplication, immutable originals, source history | [Data model](architecture/data-model.md), [Ingestion](design/media-ingestion.md), [ADR-0002](decisions/0002-immutable-media-identity.md) | 1 | `db.models`, `media.files/ingestion/scan`, `test_media_files.py`, `test_media_ingestion.py`, real Docker/API corpus | Locked in 0.1.0-rc.6 |
| MEDIA-009 | Trash never physically deletes media | [Evaluation](design/evaluation.md), [ADR-0002](decisions/0002-immutable-media-identity.md), [Phase 4 verification](development/phase-4-manual-evaluation.md) | 4 | `evaluation.service`, disposition revisions, live API/browser Trash/restore check | Locked in 0.1.0-rc.6 |
| MEDIA-010–015 | Imported spatial-video variants, validated availability, atomic replacement, independent preference, range delivery | [Data model](architecture/data-model.md), [Ingestion](design/media-ingestion.md), [API](interfaces/api-and-integrations.md), [ADR-0011](decisions/0011-imported-media-variants.md), [backend update](development/spatial-video-variant-backend-update.md) | Spatial-video update | `db.models.MediaVariant`, `media.variants`, `media.spatial_video`, variant routes/worker, `0011_spatial_video_variants`, `test_media_variants.py`, `test_variant_api.py`, `test_spatial_video_validation.py`, optional `test_private_spatial_video_fixture.py` | Implemented and real Apple fixture verified locally; packaged amd64/Vision Pro acceptance pending |
| ING-001–016 | Browser/NAS/machine-client import, inventory, stages, formats, proxies, durability | [Ingestion](design/media-ingestion.md), [API](interfaces/api-and-integrations.md), [ComfyUI upload integration](interfaces/comfyui-custom-node-upload.md), [ADR-0003](decisions/0003-separate-background-worker.md), [Phase 1 verification](development/phase-1-media-ingestion.md) | 1, rc.7 | `routes.imports/media/jobs`, bearer-token auth tests, worker actors, core ingestion services, integration tests, Docker/API/browser verification | Locked in 0.1.0-rc.7 |
| WF-001–011 | Raw workflow preservation, graph, versioned observations, plain prompts, correctable prompt roles | [Workflow intelligence](design/workflow-intelligence.md), [Data model](architecture/data-model.md), [ADR-0004](decisions/0004-layered-workflow-interpretation.md), [Phase 2 verification](development/phase-2-workflow-evidence.md) | 2, rc.8 | `workflow.evidence/graph/extraction`, prompt-role graph inference and ordering, workflow API/UI, synthetic and 14-file private golden corpus, immutable-reprocessing integration test | Locked in 0.1.0-rc.8 |
| NODE-001–010 | Offline node registry, API snapshots, automatic inference, corrections | [Workflow intelligence](design/workflow-intelligence.md), [ADR-0005](decisions/0005-offline-node-registry.md), [Phase 3 verification](development/phase-3-node-model-registries.md) | 3 | `registry.nodes/sync`, registry API/UI, `test_registry_contracts.py`, `test_registry_resolution.py`, live correction/reprocessing and offline-cache checks | Locked in 0.1.0-rc.6 |
| NODE-011 | Full visual rule-authoring system | [MVP scope](product/mvp-scope.md), [Workflow intelligence](design/workflow-intelligence.md) | Deferred | Deferred-scope guard | Deferred |
| NODE-012 | Active-only expansion of structured multi-LoRA values | [Workflow intelligence](design/workflow-intelligence.md), [Data model](architecture/data-model.md) | rc.4 | `registry.nodes._mapped_observation_values`, `test_structured_lora_mapping.py` | Locked in 0.1.0-rc.6 |
| MODEL-001–014 | Canonical/historical model registry and usage context | [Model registry](design/model-registry.md), [ADR-0006](decisions/0006-model-registry-identity.md), [Phase 3 verification](development/phase-3-node-model-registries.md) | 3 | `registry.client/models/sync`, registry API/UI, `test_registry_contracts.py`, `test_registry_resolution.py`, 14-file live Docker corpus | Locked in 0.1.0-rc.6 |
| MODEL-015–017 | Collision-safe, reversible reference-alias identity groups | [Model registry](design/model-registry.md), [ADR-0006](decisions/0006-model-registry-identity.md), [Data model](architecture/data-model.md) | rc.6 | `registry.aliases`, alias API/UI, `test_model_reference_aliases.py`, group-aware media/review/analytics regressions | Locked in 0.1.0-rc.6 |
| LORA-001–005 | Opaque local LoRA training series and step parsing | [Model registry](design/model-registry.md), [Phase 3 verification](development/phase-3-node-model-registries.md) | 3 | Exact suffix unit test, private corpus, merge/split/step correction and automatic re-resolution regression | Locked in 0.1.0-rc.6 |
| LIB-001, LIB-005 | Source-root media filtering API and directly navigable paginated gallery | [Frontend UX](design/frontend-ux.md), [Data model](architecture/data-model.md) | 1, post-rc.11 | Media list API, shared top/bottom pagination, `pageOffsetForNumber`, `paginationItems`, `media-view.test.ts`, `library-page.test.tsx`, browser verification | Implemented |
| LIB-002–004 | Static collections, saved filters, manual tags | [Frontend UX](design/frontend-ux.md), [Data model](architecture/data-model.md), [Phase 4 verification](development/phase-4-manual-evaluation.md) | 4 | Evaluation API routes, `library-page.tsx`, live PostgreSQL/API/browser scope checks | Locked in 0.1.0-rc.6 |
| LIB-006 | Visible/filterable processing, workflow, and registry errors | [Frontend UX](design/frontend-ux.md), [Ingestion](design/media-ingestion.md), [Phase 3 verification](development/phase-3-node-model-registries.md) | 1, 2, 3 | Job/import UI, workflow status/filter/detail, registry filters, durable sync history, browser validation | Locked in 0.1.0-rc.6 |
| LIB-007–009 | Deterministic library sorting, alias-aware model filters, and exact-card context-preserving detail traversal | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md) | rc.4, rc.6, post-rc.11 | Media list/navigation API integration test, alias group integration tests, URL-backed UI-only return anchor, `media-view.test.ts`, frontend type/lint/build checks | Implemented |
| LIB-010 | Laptop-friendly 2:3 portrait gallery grid | [Frontend UX](design/frontend-ux.md) | rc.7 | CSS contract, frontend lint/type/build checks, live MacBook-width browser verification | Locked in 0.1.0-rc.7 |
| LIB-011–012 | Server-resolved bulk scopes and explicit Any/All multi-model filters | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md) | rc.8 | Media/review API integration tests, `media-view.test.ts`, Library browser workflow | Locked in 0.1.0-rc.8 |
| LIB-013–014 | Persistent icon-rail navigation and preview-first media workspaces | [Frontend UX](design/frontend-ux.md) | rc.8 | `app-shell.test.tsx`, media-detail API regression, frontend checks/build, image/video browser verification | Locked in 0.1.0-rc.8 |
| LIB-015 | Durable Favorite/spatial preferences and reusable Boolean filters | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md), [Data model](architecture/data-model.md) | rc.10, spatial-video update | `0010_media_preferences`, `0011_spatial_video_variants`, media preference/filter integration regression, `media-view.test.ts`, frontend checks/build | Implemented with deprecated alias compatibility |
| LIB-016 | Collapsible right-side Library controls sidebar with hidden scrollbar and responsive stacked fallback | [Frontend UX](design/frontend-ux.md) | post-rc.11 | `library-page.tsx`, `library-page.test.tsx`, responsive CSS, frontend lint/type/build checks, desktop and compact browser verification | Implemented |
| LIB-017 | Confirmed video-only spatial-variant attachment with observable processing, safe replacement, and retry | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md), [ADR-0011](decisions/0011-imported-media-variants.md) | post-rc.11 | `spatial-variant-attachment.tsx`, `spatial-variant-attachment.test.tsx`, frontend lint/type/build checks, live MOV upload verification | Implemented; live browser upload verification pending |
| LIB-018 | Hands-off looping slideshow for filtered media or collections with optional seeded shuffle | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md) | post-rc.11 | `get_slideshow_playlist`, `test_slideshow_playlist_resolves_collections_and_seeded_shuffle`, `slideshow-page.tsx`, `slideshow-page.test.tsx`, `media-view.test.ts`, frontend checks/build | Implemented; live browser playback verification pending |
| LIB-019 | Complete-library case-insensitive keyword search across current prompts and checkpoint/LoRA identities | [Frontend UX](design/frontend-ux.md), [API](interfaces/api-and-integrations.md) | post-rc.14 | Shared backend media keyword filter, media-library integration regressions, URL-backed Library search control, `media-view.test.ts`, `library-page.test.tsx`, backend/frontend checks and builds | Implemented; live browser search verification pending |
| EVAL-001–019 | Templates, criteria, states, review, autosave, revisions | [Evaluation](design/evaluation.md), [Frontend UX](design/frontend-ux.md), [ADR-0007](decisions/0007-versioned-manual-evaluation.md), [Phase 4 verification](development/phase-4-manual-evaluation.md) | 4 | `evaluation.catalog/service`, evaluation/review API, review UI, `test_evaluation.py`, `review.test.ts`, migration, live API/browser checks | Locked in 0.1.0-rc.6 |
| EVAL-020–022 | Context-visible single-media evaluation and durable per-media optional modules | [Evaluation](design/evaluation.md), [Frontend UX](design/frontend-ux.md), [Data model](architecture/data-model.md), [API](interfaces/api-and-integrations.md) | rc.8 | `0009_media_evaluation_modules`, evaluation-context/module API regression, shared frontend control tests, Media Detail browser traversal | Locked in 0.1.0-rc.8 |
| AN-001–014 | Observational model reports, statistics, saved runs | [Analytics](design/analytics.md), [ADR-0008](decisions/0008-observational-analytics.md), [Phase 5 verification](development/phase-5-model-analytics.md) | 5 | `analytics.service/statistics`, analytics API/UI, `test_analytics_statistics.py`, `test_analytics_reports.py`, `test_analytics.py`, migration and live Docker/browser checks | Locked in 0.1.0-rc.6 |
| OPS-001–004, OPS-006, OPS-010 | AMD64 Compose, separate API/worker, PostgreSQL, Redis/Dramatiq, uv, Alembic | [Architecture](architecture/system-overview.md), [Deployment](operations/deployment-and-security.md), [Phase 0 verification](development/phase-0-foundation.md) | 0 | `compose.yaml`, Dockerfiles, AMD64 builds, empty-DB migration and drift check | Locked in 0.1.0-rc.6 |
| OPS-005 | Mounted filesystem storage for originals/derivatives | [Deployment](operations/deployment-and-security.md), [Ingestion](design/media-ingestion.md) | 1 | Compose mounts and real derivative/original verification | Locked in 0.1.0-rc.6 |
| OPS-007–009 | Backup/restore and portable export | [Recovery](operations/backup-recovery-observability.md), [Phase 6 verification](development/phase-6-nas-release.md) | 6 | `deploy/operations`, `operations.exports`, `routes.exports`, export/status tests, local and NAS restore rehearsals | Locked in 0.1.0-rc.6 |
| OPS-011 | Bounded J4125 background concurrency | [Deployment](operations/deployment-and-security.md), [Phase 6 verification](development/phase-6-nas-release.md) | 0, 1, 6 | One-process/one-thread worker, Compose limits, 1,036-path real J4125 scan with responsive review/status API | Locked in 0.1.0-rc.6 |
| OPS-012–014 | Isolated Mac development and pull-only milestone deployment | [Mac-first workflow](development/mac-first-development-and-release.md), [Deployment](operations/deployment-and-security.md), [Upgrade runbook](operations/upgrade-runbook.md) | rc.8 | `compose.development.yaml`, development/release scripts, `release-images.yml`, `test_operational_workflows.py`, local smoke test, first milestone rehearsal | Locked in 0.1.0-rc.8 |

## Critical invariant traceability

| Invariant | Requirements | ADR/design | Required regression |
|---|---|---|---|
| Embedded ground truth never changes | WF-001, WF-002 | ADR-0004, workflow intelligence | Raw payload hash unchanged after reprocessing |
| Original media never changes | MEDIA-007 | ADR-0002, ingestion | `test_exact_hash_dedup_preserves_one_immutable_original` + Docker corpus |
| Imported variants never replace original identity or workflow evidence | MEDIA-010 | ADR-0011, ingestion | Variant activation regression plus unchanged `MediaAsset` hash/workflow snapshot |
| Failed spatial replacement preserves the prior active variant | MEDIA-011–014 | ADR-0011, backend update guide | Variant replacement/failure transaction regression |
| Filename is never media identity | MEDIA-001, MEDIA-005, MEDIA-006 | ADR-0002 | Scan same-name/different-byte integration and Docker corpus |
| Exact duplicates share evaluation history | MEDIA-003, MEDIA-004 | ADR-0002, data model | Unit/integration plus upload-to-source dedup Docker check |
| Unknown parser/model data does not block import | ING-009, WF-005, WF-008, MODEL-005 | ADR-0004/0006 | Unknown/malformed golden cases |
| ComfyUI is not a runtime dependency | NODE-002, NODE-003 | ADR-0005/0010 | Unreachable-source sync plus cached registry query |
| Manual corrections outrank inference | NODE-008, LORA-004 | Workflow intelligence, model registry | Mapping/reprocessing and merge/split re-resolution regressions |
| Structured LoRA loaders link only active entries | NODE-012, WF-001, WF-002 | Workflow intelligence, data model | `test_structured_lora_mapping.py`; raw collection remains unchanged |
| Civitai absence is not local failure | MODEL-003, MODEL-004, MODEL-011 | Model registry | Optional-stage partial outcome and local-only artifact fixture |
| Alias grouping never rewrites evidence or bridges conflicting artifacts | MODEL-015–017, WF-001, WF-002 | ADR-0006, model registry | `test_model_reference_aliases.py`; raw values unchanged, collision rejected, revoke restores identities |
| Missing historical criterion is not zero | EVAL-005–008, AN-014 | ADR-0007, analytics | `test_adding_character_module_keeps_completed_core_snapshot_complete`; `test_shared_criteria_never_impute_missing_values_as_zero` |
| Trash preserves data and never auto-advances | MEDIA-009, EVAL-010–013 | Evaluation | `test_trash_is_reversible_and_version_conflicts_do_not_overwrite` + live browser same-position check |
| Saved analysis never changes | AN-010, AN-011 | ADR-0008, analytics | `test_saved_run_is_immutable_and_rerun_uses_current_score_revision` + live linked rerun |
| Redis is not authoritative | OPS-003, OPS-004 | ADR-0003, architecture | `test_job_recovery.py` + live stopped/restarted-worker queued export |
| Backups protect manual work | OPS-007–010 | Recovery | Local and real-NAS disposable restore rehearsals |

## V1 rubric traceability

| Criterion ID | Requirement/design source | Seed/migration | UI test | Analysis test |
|---|---|---|---|---|
| `core.aesthetic_appeal` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Live image/video review + `test_evaluation.py` | Stable-key raw/composite analytics + live core report |
| `core.composition` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Live N/A/Clear review check + `test_evaluation.py` | Stable-key raw/composite analytics + N/A regression |
| `core.prompt_adherence` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Exact-prompt blind UI check | Stable-key raw/composite analytics |
| `core.logical_plausibility` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Live image/video review | Stable-key raw/composite analytics |
| `core.technical_execution` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Live image/video review | Stable-key raw/composite analytics |
| `core.artifact_cleanliness` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video core V1 | Live image/video review | Stable-key raw/composite analytics |
| `video.temporal_consistency` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / video core V1 | 8-file video corpus + 9-control browser check | Stable-key raw/composite analytics |
| `video.motion_quality` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / video core V1 | 8-file video corpus + 9-control browser check | Stable-key raw/composite analytics |
| `video.sequence_coherence` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / video core V1 | 8-file video corpus + 9-control browser check | Stable-key raw/composite analytics |
| `character.identity_fidelity` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video character V1 | Supplemental-preservation regression + live image review | Module-filtered stable-key analytics |
| `character.identity_adaptability` | [Evaluation](design/evaluation.md) | `0005_manual_evaluation` / image+video character V1 | Supplemental-preservation regression + live image review | Module-filtered stable-key analytics |

## MVP report traceability

| Report | Requirements | Design | Planned test |
|---|---|---|---|
| Checkpoint profile | AN-003–009 | Analytics: report 1 | `test_all_six_reports_produce_boundary_aware_groups` + live checkpoint table |
| Checkpoint-pair profile | MODEL-012–014, AN-006 | Analytics: report 2 | Ordered pair in `test_all_six_reports_produce_boundary_aware_groups` |
| LoRA profile | AN-006 | Analytics: report 3 | Multi-LoRA involvement in `test_all_six_reports_produce_boundary_aware_groups` |
| LoRA training-series trend | LORA-001–005, AN-006 | Analytics: report 4 | Numeric step fixture + live `Krea2_guzong_lora_v2` plot |
| Checkpoint-by-LoRA matrix | AN-006 | Analytics: report 5 | Four-cell cross-product fixture and matrix UI |
| LoRA-combination profile | AN-006 | Analytics: report 6 | Order-independent exact set fixture |

## Deferred-scope guard

| Deferred capability | Scope source | Guard |
|---|---|---|
| Automated benchmarks/GPU evaluation | [MVP scope](product/mvp-scope.md) | No evaluator tables/workers/providers in MVP |
| Visual/perceptual deduplication | MVP scope, ADR-0002 | Dedup API accepts exact SHA only |
| Strict prompt-controlled comparison | MVP scope, ADR-0008 | No default prompt balancing/matching |
| Dedicated sampler/LoRA-strength reports | MVP scope, analytics | No MVP report type |
| Full visual parser-rule editor | MVP scope, ADR-0005 | Unknown inbox + mappings only |
| Multi-user/RBAC | MVP scope, ADR-0009 | One administrator principal |
| ComfyUI instance tracking | MVP scope, ADR-0010 | No instance domain table |
| Direct ComfyUI custom-node ingestion | MVP scope | Generic bearer upload endpoint exists; node package remains deferred |
| Hugging Face enrichment | MVP scope | No provider adapter in MVP |
| Physical purge | MVP scope, ingestion | No destructive media endpoint |

## Implementation update rules

When a requirement is implemented:

1. Change Status from `Documented` to `Implemented`.
2. Add code/module references.
3. Add exact test references.
4. Record the first release containing it.
5. Do not mark a range Implemented if only a subset is complete; split the row.

When a requirement changes:

1. Update the requirement text without reusing retired IDs.
2. Add/supersede an ADR when architecture or invariants change.
3. Update the affected design.
4. Update this matrix and regression coverage.
