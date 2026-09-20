# Project Comfy Gallery Context Map

Use this map to load only the domain context relevant to the current role while
still respecting project-wide decisions.

## Project-wide context

- Product and engineering documentation index: `doc/README.md`
- Shared glossary: `doc/glossary.md`
- System architecture: `doc/architecture/system-overview.md`
- System-wide ADRs: `doc/decisions/`
- API contract: `doc/interfaces/api-and-integrations.md`
- Requirements traceability: `doc/requirements-traceability.md`

## Main full-stack context

**Boundary:** repository root excluding `mobile/`, `XR/`, and `Quest/`.

**Owns:** FastAPI, worker, shared Python core, PostgreSQL schema/migrations, React
web application, ingestion, managed storage, and deployment.

Read:

- `README.md`
- `doc/README.md`
- The relevant documents under `doc/product/`, `doc/architecture/`, `doc/design/`,
  `doc/interfaces/`, and `doc/operations/`

## Mobile context

**Boundary:** `mobile/`.

**Owns:** native iPhone/iPad client behavior and its backend integration.

Read in order:

- `mobile/README.md`
- `mobile/product-requirements.md`
- `mobile/ui-ux-design.md`
- `mobile/api-contract.md`
- `mobile/development-handoff.md`

The backend remains authoritative when a mobile document and implemented server
behavior differ.

## XR context

**Boundary:** `XR/`.

**Owns:** native Apple Vision Pro client behavior, RealityKit runtime spatial-image
conversion, and spatial-video playback after the backend contract supports it.

Read in order:

- `XR/README.md`
- `XR/research-findings.md`
- `XR/product-requirements.md`
- `XR/spatial-ui-ux-design.md`
- `XR/api-and-media-contract.md`
- `XR/development-handoff.md`

The backend remains authoritative for stored media, preferences, and variant
availability. Runtime spatial-image objects remain XR-owned and are not backend
variants.

## Quest context

**Boundary:** `Quest/`.

**Owns:** the standalone Meta Quest client, controller interaction, Android build
and tests, ordinary media presentation, and optional compatible spatial playback.

**Status:** Kotlin/Compose/Meta Spatial SDK client implemented through 0.3.0;
remaining physical-device acceptance is tracked in `Quest/device-validation.md`.

Read in order:

- `Quest/README.md`
- `Quest/product-requirements.md`
- `Quest/ui-ux-design.md`
- `Quest/api-and-media-contract.md`
- `Quest/development-plan.md`

Platform evidence lives in `doc/research/quest-3-development-research.md`.
The backend remains authoritative for media identity, variants, and preferences.
Quest capability is separate from stored spatial availability; optional stereo
work must not block the ordinary viewer or replace an Apple variant with SBS.

## Cross-context spatial-video work

Read both:

- GitHub tracking issue
  [`#2`](https://github.com/blkot/ProjectComfyGallery/issues/2)
- `doc/development/spatial-video-variant-backend-update.md`

Dependency order:

1. Main/backend contract and deployment.
2. External Windows pipeline integration against that contract.
3. XR client update and physical Vision Pro verification.

Do not start the XR contract migration from an unimplemented backend proposal.
