# Project Comfy Gallery

Self-hosted ComfyUI media intelligence, manual evaluation, and observational model analysis.

The governing product and engineering documentation starts at [doc/README.md](doc/README.md).

**Locked release candidate:** `0.1.0-rc.9`. Runtime images use the same tag and
OCI version label; upstream base images are pinned by digest.

## MVP release status

Phases 0–6 are implemented and verified, including the real x86 J4125 NAS release:

- FastAPI API service.
- Separate Dramatiq worker.
- Shared PostgreSQL/configuration/authentication package.
- Alembic migrations.
- React/TypeScript/Vite web application.
- Docker Compose with PostgreSQL, Redis, API, worker, and web services.
- Single-user login, database-backed sessions, CSRF protection, and revocable API tokens.
- Health/readiness/system-status endpoints.
- Authenticated multi-file browser uploads.
- Read-only NAS source registration and manually triggered recursive rescans.
- UUIDv7 media identity, streaming SHA-256, and exact-byte deduplication.
- Immutable hash-addressed original storage and source-path history.
- PNG/JPEG/WebP and MP4/WebM content validation and probing.
- Versioned image thumbnails, video posters, and H.264 browser proxies.
- Durable job, stage-attempt, scan-batch, and upload-batch records.
- Media Library, Imports, Jobs, and Media Detail pages, including deterministic
  sorting and context-preserving Previous/Next viewing.
- Immutable decoded workflow evidence with independent API-prompt and visual-workflow
  states.
- PNG/JPEG/WebP and MP4/WebM embedded metadata readers.
- Unknown-safe generic nodes, edges, named inputs, widget values, and queryable values.
- Versioned extraction runs with evidence hashes that remain stable during reprocessing.
- First-pass checkpoint, LoRA, prompt, and generation-parameter observations with
  confidence and provenance.
- Workflow status filtering, raw evidence loading, graph search, node inspection, and
  extraction history in the frontend.
- Per-media reprocessing and bulk backfill for media imported before Phase 2.
- A private golden-corpus regression harness with stable hash-based case identities.
- Versioned ComfyUI `/object_info` snapshots and schema-fingerprinted node definitions.
- First-pass checkpoint, LoRA, prompt, and parameter mappings with manual corrections.
- LoRA Manager local scan, optional Civitai enrichment, and staged durable sync status.
- Canonical, ambiguous, and workflow-only historical model references.
- Per-workflow model usage classified by pipeline pattern and slot.
- Correctable local LoRA training series with step edit, merge, and split.
- Explicit user-managed model comparison groups.
- Node Registry and Model Registry pages with cached offline queries.
- Locked, versioned image/video/character evaluation templates.
- Nullable 0–10 scores with real zero, explicit N/A/Clear, and immutable revisions.
- Derived Not started, In progress, and Complete states plus reversible Trash.
- Resumable, stable or seeded-random review sessions.
- Review pools from selection, collection, source directory, filter, saved filter,
  random media, or the global In progress pool.
- Configuration-blind image/video review with exact prompts, autosave, undo, keyboard
  navigation, and no automatic advance.
- Library collections, tags, saved filters, selection actions, evaluation filters,
  and exact checkpoint/LoRA filters.
- Structured multi-LoRA loader extraction that links only explicitly active entries
  while retaining the full raw embedded value.
- Six checkpoint/LoRA reports with architecture, pipeline, slot, ordered-pair, and
  local-series boundaries.
- Shared-criterion composites with versioned weighting profiles and no missing-value
  imputation.
- Distributions, coverage, quartiles, deterministic bootstrap intervals, and
  reference-based Cliff's delta.
- Live analysis preview, immutable saved runs, linked reruns, and exact media
  drill-down.
- LoRA training-step trend and sparse checkpoint-by-LoRA matrix views.
- Scheduled PostgreSQL backups with daily/weekly retention, checksum manifests, and
  guarded restore.
- Durable authenticated JSON/CSV exports that exclude authentication secrets.
- Worker heartbeat and startup recovery of interrupted durable jobs.
- Operational status for worker freshness, durable queues, disk pressure, backup
  age, and recent scan/sync/export activity.
- Production Compose with private database/broker ports, resource ceilings, and
  rotated logs.
- Login rate limiting and browser security headers.
- Python and frontend checks in CI.

## Prerequisites

- Docker with Compose, or:
- Python 3.13 managed by `uv`.
- Node.js and pnpm 11.
- PostgreSQL and Redis for a non-container local run.

## Start with Docker Compose

```bash
cp .env.example .env
```

Edit `.env` and replace both password placeholders, then run:

```bash
docker compose up --build
```

Open <http://localhost:8080> and sign in with `CG_ADMIN_USERNAME` and
`CG_ADMIN_PASSWORD`.

To enable one-click node/model synchronization, set the LAN URL of the ComfyUI
installation that hosts LoRA Manager:

```dotenv
CG_COMFYUI_BASE_URL=http://192.168.x.x:8188
```

ComfyUI only needs to be online during a manual synchronization. Cached registries
remain usable while it is offline.

By default:

- Managed originals and derivatives are stored under `./data/media`.
- The host directory `./data/import` is mounted read-only as `/imports`.
- Register `/imports` (or a subdirectory) from the Imports page, then trigger a scan.

To use existing NAS directories, set absolute host paths in `.env`:

```dotenv
MEDIA_DATA_ROOT=/volume1/docker/comfy-gallery/media
IMPORT_ROOT=/volume1/comfyui/output
```

The application never modifies `IMPORT_ROOT`; imported originals are preserved in
`MEDIA_DATA_ROOT`.

## Production NAS deployment

Set absolute NAS paths and the public origin in `.env`:

```dotenv
MEDIA_DATA_ROOT=/share/ComfyGallery/media
IMPORT_ROOT=/share/ComfyUI/output
BACKUP_ROOT=/share/ComfyGallery/backups
CG_ALLOWED_ORIGINS=http://192.168.50.68:8080
TZ=Asia/Shanghai
```

Source files must be readable by container UID 10001; the import mount stays
read-only. Start the production topology:

```bash
make production
```

Only the web port is published. Open `/operations` after login to verify disk,
worker, queue, and backup state. Run an immediate database backup with:

```bash
make backup
```

Database dumps protect PostgreSQL/manual work. Include `MEDIA_DATA_ROOT` and
`BACKUP_ROOT` in the NAS snapshot or off-device backup policy. Read the
[recovery runbook](doc/operations/backup-recovery-observability.md) and
[upgrade runbook](doc/operations/upgrade-runbook.md) before restoring or upgrading.

## Local development

Mac development uses isolated local data, a separate PostgreSQL/Redis Compose
project, native FastAPI/worker processes, and Vite hot reload:

```bash
make dev
```

Open <http://127.0.0.1:5173>. The first run creates the ignored
`.env.development`, installs dependencies, starts local infrastructure, applies
migrations, and creates the local administrator. It never uses the NAS database or
managed media.

See [Mac-first development and milestone releases](doc/development/mac-first-development-and-release.md)
for commands, data isolation, GitHub-built AMD64 milestone images, and pull-only
NAS deployments.

## Checks

```bash
make check
make audit
make image-audit
```

`make image-audit` builds and scans the final amd64 runtime images, so it takes
longer than the normal code test suite.

Phase-specific implementation and validation evidence is recorded in
[Phase 1 media ingestion](doc/development/phase-1-media-ingestion.md) and
[Phase 2 workflow evidence](doc/development/phase-2-workflow-evidence.md), and
[Phase 3 node/model registries](doc/development/phase-3-node-model-registries.md), and
[Phase 4 manual evaluation](doc/development/phase-4-manual-evaluation.md), and
[Phase 5 model-focused analytics](doc/development/phase-5-model-analytics.md), and
[Phase 6 NAS release](doc/development/phase-6-nas-release.md).

## Requirement traceability

Accepted behavior is defined by stable IDs in
[product requirements](doc/product/requirements.md). Implementation coverage is tracked in
[requirements traceability](doc/requirements-traceability.md).
