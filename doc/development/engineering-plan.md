# Engineering Plan and Delivery Roadmap

**Status:** MVP phases 0–6 implemented and verified

**Locked release candidate:** `0.1.0-rc.7`

## Delivery strategy

Build vertical, testable slices that preserve the core invariants from the beginning. Avoid creating a visual-only prototype with throwaway data structures; media identity, immutable evidence, migrations, and durable job state must exist before large-scale import.

## Implemented monorepo layout

```text
/
  apps/
    api/                  FastAPI application
    worker/               Dramatiq actors and worker entrypoint
    web/                  React/TypeScript SPA
  packages/
    py/
      core/               Shared domain, configuration, security, database, migrations
  tests/
    unit/
    integration/
    api/
  testdata/
    golden/               Local/private representative media corpus
    synthetic/            Small committed generated fixtures
  deploy/
    docker/
  doc/
  compose.yaml
  pyproject.toml
  uv.lock
  package.json
  pnpm-lock.yaml
```

The Phase 0 scaffold deliberately starts with one shared Python core package. It
MUST split into focused media, workflow, integration, and analytics packages
when those domains become substantial; package boundaries are not created only
to leave them empty. The following boundaries remain required:

- Domain/extraction logic must be testable without HTTP.
- Worker actors call shared services rather than duplicate business logic.
- External integrations live behind adapters.
- Frontend consumes an explicit API contract.

## Backend conventions

- Python versions and dependencies managed with `uv`.
- Type annotations required for public interfaces.
- FastAPI/Pydantic at the HTTP boundary.
- SQLAlchemy and Alembic for database access/migrations.
- Domain services avoid importing FastAPI.
- Transactions are explicit at command boundaries.
- Structured errors have stable codes.
- External HTTP calls use bounded timeout/retry policies.
- CPU/blocking file work does not run on the async API event loop.

The accepted foundation toolchain is:

- Ruff.
- mypy in strict mode.
- pytest.

## Frontend conventions

- React with TypeScript and Vite.
- Generated or schema-derived API types where practical.
- TanStack Query for server state.
- React Router for navigation.
- Virtualization for large lists.
- Component state must not duplicate authoritative score/job state without reconciliation.
- Accessibility tests for review controls.

- pnpm 11 manages the frontend workspace.
- The Phase 0 shell uses plain CSS and no component-library dependency.
- Route pages are lazy-loaded and TanStack Query owns server state.
- The desktop shell supports a persistent icon rail; media record and review routes
  use viewport-height preview/inspector workspaces with independent inspector scrolling.

## Branch and review discipline

- Small, requirement-scoped changes.
- `main` is continuously tested source; production deploys only explicit annotated
  milestone tags.
- Every PR/commit references requirement IDs in description where practical.
- Schema changes include migrations and migration tests.
- Parser changes include golden/synthetic fixture updates.
- Evaluation changes include state-transition and migration tests.
- Architectural changes update an ADR.

Daily implementation runs on the Mac against the isolated development Compose
infrastructure. GitHub Actions builds immutable `linux/amd64` milestone images;
the NAS pulls and verifies them without compiling. See
[Mac-first development and milestone releases](mac-first-development-and-release.md).

## Phase 0: repository foundation

**Implementation status:** Complete on 2026-07-23. See
[Phase 0 foundation and verification](phase-0-foundation.md).

Deliverables:

- Monorepo/application structure.
- `uv` Python workspace and frontend workspace.
- Dockerfiles and development Compose.
- PostgreSQL/Redis connectivity.
- FastAPI liveness/readiness.
- Worker heartbeat/test actor.
- Alembic baseline.
- Single-user authentication skeleton.
- CI for formatting, types, unit tests, build.

Exit criteria:

- Fresh checkout can start locally with one documented command.
- API, worker, database, Redis, and frontend report healthy.
- Migration upgrade from empty database succeeds.
- No production secret is committed.

Verified outcomes:

- `docker compose up --build` starts PostgreSQL, Redis, API, worker, and web.
- Empty-database migration and Alembic schema-drift checks pass.
- Browser login, session, CSRF rejection, bearer-token creation/use/revocation,
  and logout pass.
- Backend and web images build successfully for `linux/amd64`.

## Phase 1: media identity and ingestion

**Implementation status:** Complete on 2026-07-23. See
[Phase 1 media ingestion and verification](phase-1-media-ingestion.md).

Deliverables:

- Media/source/job schema.
- Browser upload.
- Source-root configuration and manual rescan.
- Streaming SHA-256 and exact deduplication.
- Managed-original placement.
- Image/video probe.
- Thumbnails/posters and proxy pipeline.
- Job/batch UI.
- Library gallery/table and media record foundation.

Exit criteria:

- Interrupted import resumes/retries safely.
- Same filename/different bytes produces distinct UUIDs.
- Same bytes/multiple paths deduplicate.
- Source rename/missing/change behaviors match requirements.
- Thousands-file synthetic scan does not exhaust memory.

Verified outcomes:

- Browser upload and manually triggered read-only source scans run through the
  separate worker.
- Exact duplicates across upload and multiple paths resolve to one media UUIDv7.
- Same filenames with different bytes remain distinct media.
- Unchanged paths skip hashing; rename, missing, and changed-path version history
  match the accepted design.
- Interrupted atomic-placement state resumes without creating another media record.
- A corrupt item produces a stable error without blocking the scan batch.
- HEVC MP4 input receives a poster and an H.264 MP4 proxy with byte-range playback.
- PostgreSQL migration upgrade and schema-drift checks pass.

The streaming traversal and bounded worker model are implemented. A private
thousands-file NAS corpus run remains an operational scale check for Phase 6, not a
schema or algorithm blocker for Phase 1.

## Phase 2: workflow evidence and parser foundation

**Implementation status:** Complete and verified in the locked `0.1.0-rc.7` tree.

Deliverables:

- Format-specific embedded metadata readers.
- Raw evidence storage.
- API-prompt and visual-workflow normalization.
- Generic graph UI/records.
- Versioned extraction runs.
- Initial built-in semantic extractors.
- Golden-corpus regression suite.

Exit criteria:

- Every golden file imports without losing original metadata. **Verified:** 14/14.
- Unknown nodes remain structurally visible. **Verified:** generic API/visual graph.
- Parser failure does not block media readiness. **Verified:** partial/malformed
  integration regression.
- Reprocessing produces new observations without mutating evidence. **Verified:**
  evidence hash unchanged across two runs.

Implementation and validation evidence is recorded in
[Phase 2 workflow evidence](phase-2-workflow-evidence.md). The supplied private corpus
is organized by stable content-hash case IDs and remains outside Git.

## Phase 3: node and model registries

**Status:** Implemented and verified

Deliverables:

- Anonymous ComfyUI object-info sync. **Implemented.**
- Node-definition fingerprinting and compatibility matching. **Implemented.**
- Automatic classification/confidence. **Implemented.**
- Unknown-node filtering and persistent corrections. **Implemented.**
- LoRA Manager adapter and staged sync. **Implemented.**
- Canonical/historical model references. **Implemented.**
- Architecture/pipeline/slot representation. **Implemented.**
- LoRA training-series inference and correction. **Implemented, including merge,
  split, and step edits.**

Exit criteria:

- Application parses using cached registries while ComfyUI is offline. **Verified.**
- High-confidence mappings work automatically. **Verified against 4,360 live
  definitions and the private corpus.**
- One correction reprocesses all affected workflows. **Verified through the live
  correction/job path.**
- Local-only no-Civitai models remain resolved. **Verified.**
- Deleted workflow-only models remain analyzable. **Verified with four historical
  references.**

Implementation and validation evidence is recorded in
[Phase 3 node and model registries](phase-3-node-model-registries.md).

## Phase 4: manual evaluation

**Implementation status:** Complete and verified on 2026-07-24. See
[Phase 4 manual evaluation and review](phase-4-manual-evaluation.md).

Deliverables:

- Seeded locked V1 criteria/anchors/templates.
- Evaluation states, N/A, Trash, and revisions.
- Review-session snapshots and In progress pool.
- Configuration-blind prompt-aware review UI.
- Nullable sliders, keyboard controls, autosave, undo.
- Collections/tags/saved filters sufficient to create review scopes.
- Server-resolved page/all-matching library selection and explicit Any/All
  multi-checkpoint/multi-LoRA filtering.

Exit criteria:

- Every state transition is tested. **Verified.**
- No action auto-navigates after completion or Trash. **Verified through live API and
  browser checks.**
- Existing scores survive template/migration tests. **Verified through clean/preserved
  PostgreSQL migration checks and supplemental-template regression.**
- Multiple-day stop/resume workflow is demonstrated. **Verified through persisted
  session cursor reload.**
- Review UI is keyboard operable. **Verified for native sliders, Clear/Delete,
  N/A, explicit buttons, and Alt-arrow navigation.**

## Phase 5: model-focused analytics

**Implementation status:** Complete and verified on 2026-07-24. See
[Phase 5 model-focused analytics](phase-5-model-analytics.md).

Deliverables:

- Filtered population builder.
- Six MVP report types.
- Statistics, distributions, bootstrap intervals, effect sizes, coverage, and warnings.
- Weighting profiles.
- Live preview and immutable saved runs.
- Drill-down to media.

Exit criteria:

- Saved runs remain unchanged after score/model correction. **Verified through
  score-revision snapshot and rerun integration coverage.**
- Rerun creates a linked new version. **Verified in integration and live browser
  checks.**
- Cross-template missing values are not treated as zero. **Verified for shared
  criteria and explicit N/A.**
- Reports respect architecture/pipeline/slot boundaries. **Verified across all six
  report grouping fixtures and the live corpus.**
- No default prompt balancing or causal language. **Verified by API/UI contract and
  report implementation.**

## Phase 6: hardening and NAS release

**Implementation status:** Complete and verified on 2026-07-24. See
[Phase 6 NAS release](phase-6-nas-release.md).

Deliverables:

- Production Compose.
- Backup/retention/restore commands.
- Portable exports.
- Resource/concurrency tuning.
- Security review.
- Operational status page.
- Upgrade documentation.

Exit criteria:

- Restore rehearsal succeeds. **Verified locally and on the real NAS.**
- J4125 bulk import and review remain responsive. **Verified with 1,036 paths,
  14 unique image/video media, and sub-136 ms worst request on the clean rescan.**
- Low-disk, integration-offline, corrupt-media, and worker-restart scenarios pass.
  **Verified through automated and live release checks.**
- Dependency and final amd64 runtime-image audits pass. **Verified with no known
  Python/production-JavaScript vulnerabilities and zero high or critical Trivy
  findings.**
- Documentation and traceability are current. **Verified.**

## Release policy

Proposed semantic versioning:

- Patch: compatible bug fixes.
- Minor: additive features/migrations.
- Major: intentional breaking API or operational changes.

Database backups are required before upgrades regardless of version category.

## Change-control rule

If implementation discovers that an accepted behavior is impractical:

1. Document evidence.
2. Update/open the relevant question.
3. Propose an ADR that changes the decision.
4. Obtain confirmation before implementing a materially different behavior.

Code must not silently redefine the product.
