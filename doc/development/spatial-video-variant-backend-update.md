# Spatial Video Variant Backend Update Guide

**Status:** Implemented on `codex/spatial-video-backend`; real Apple MV-HEVC
validation passes locally, while packaged-image and Vision Pro acceptance remain
pending

**Date:** 2026-07-29

**Scope:** Main Project Comfy Gallery backend, API, database, and backend-facing
web compatibility. This document does not implement or specify the XR player and
does not specify the Windows spatial-video conversion toolchain.

## Purpose

Upgrade the Gallery so one logical video media record can own its immutable
original file and an externally generated Apple spatial MV-HEVC variant.

The intended external production flow is:

```text
ComfyUI original video
    -> ml-sharp SBS video
    -> MV-HEVC encoding
    -> Apple spatial metadata mux/injection
    -> import completed spatial video as a variant of the original Gallery media
```

The converter is outside the Gallery backend. The Gallery accepts only the
completed spatial output. Embedding ComfyUI workflow metadata in that output is
optional; the workflow snapshot extracted from the immutable original remains
canonical.

## Accepted product semantics

### Logical media and physical files

- A `Media` remains the logical gallery item and continues to own one evaluation
  history, workflow snapshot, favorite state, collections, tags, and user playback
  preference.
- `MediaAsset` remains the one-to-one immutable original. Do not replace it with
  the variant table during this update.
- A new `MediaVariant` is a first-class alternate playable file attached to the
  same `Media`.
- Existing `Derivative` rows remain regenerable posters, thumbnails, and browser
  proxies. A spatial video is not a `Derivative`: the Gallery backend cannot
  cheaply regenerate it, it is imported externally, and clients may deliberately
  select it for full-fidelity playback.
- SBS video and intermediate non-spatial MV-HEVC files are pipeline artifacts.
  They are not imported by this first backend update.

### Spatial image and spatial video are different

- Spatial images continue to use Vision Pro runtime conversion. No spatial-image
  file or backend variant is introduced here.
- A video is spatially available only when it has an active, ready, validated
  `spatial_video` variant.
- `spatial_available` is system-owned video state. Users cannot edit it.
- `prefer_spatial_playback` is user-owned intent shared by image and video media.
- Importing, replacing, failing, or removing a spatial variant must not change
  `favorite` or `prefer_spatial_playback`.

Effective playback intent is:

```text
image:
    prefer_spatial_playback
        ? request/use the client runtime spatial presentation
        : show the original image

video:
    prefer_spatial_playback && spatial_available
        ? play the active spatial video variant
        : play the ordinary original/proxy path
```

Availability and preference must remain independent. If a spatial variant becomes
unavailable, ordinary video playback is the fallback. The stored user preference
may remain true so it can be honored again after a valid replacement is imported.

## Non-goals

- Implementing or choosing the Windows SBS-to-spatial conversion tools.
- Running ml-sharp or MV-HEVC conversion on the NAS worker.
- Runtime conversion of video in XR.
- Quest, Android, or other stereo delivery formats.
- Exporting RealityKit-generated spatial images.
- Replacing the existing immutable-original identity or SHA-256 deduplication
  model.
- Storing SBS intermediate files in the Gallery.
- Requiring the spatial file to contain embedded ComfyUI workflow JSON.

## Why `MediaAsset` should remain the original

The current identity invariant is based on the exact bytes of the imported
original:

- `MediaAsset.sha256` resolves exact duplicates to one logical `Media`.
- Workflow extraction reads the original.
- Source occurrences describe where the original was discovered.
- Existing detail, sorting, download, and ingestion code assumes `Media.asset` is
  present and immutable.

Keeping this relationship avoids a high-risk rewrite and preserves all current
identity behavior. `MediaVariant` adds alternate playback without changing which
file is the original or which file provides canonical workflow evidence.

## Proposed database model

### `media` additions and rename

Add:

```text
spatial_available boolean not null default false
```

Rename the persisted user preference for clarity:

```text
spatial_view_preferred -> prefer_spatial_playback
```

The rename does not change existing values. A compatibility API field and endpoint
must remain temporarily available because the backend will be deployed before XR
is updated.

`spatial_available` is a synchronized projection of active, ready spatial-video
variants. The variant rows remain the source of truth.

### `media_variant`

Recommended first schema:

```text
id                    uuid primary key
media_id              uuid not null references media(id) on delete cascade
role                  varchar(32) not null
status                varchar(32) not null
is_active             boolean not null default false
sha256                varchar(64) null
byte_size             bigint null
original_filename     varchar(1024) not null
original_extension    varchar(32) null
managed_path          varchar(1024) null
detected_format       varchar(32) null
mime_type             varchar(128) null
width                 integer null
height                integer null
duration_seconds      double precision null
frame_rate            double precision null
container             varchar(64) null
video_codec           varchar(64) null
audio_codec           varchar(64) null
probe_data            jsonb not null default '{}'
validation_data       jsonb not null default '{}'
converter_name        varchar(128) null
converter_version     varchar(64) null
source_asset_sha256   varchar(64) null
created_at            timestamptz not null
updated_at            timestamptz not null
ready_at              timestamptz null
last_error_code       varchar(80) null
last_error_message    text null
```

Accepted values for the first implementation:

```text
role:
    spatial_video

status:
    staging
    processing
    ready
    duplicate
    failed
```

Use string columns plus application validation, matching existing model
conventions, rather than PostgreSQL enums that are harder to extend.

Required constraints and indexes:

- Index `media_id`.
- Index `(media_id, role, status)`.
- Unique `managed_path` when non-null.
- Unique `sha256` when non-null.
- PostgreSQL partial unique index on `(media_id, role)` where `is_active = true`.
- Check that an active row has `status = 'ready'`, or enforce the equivalent
  invariant in the one service responsible for activation.

`sha256`, file facts, `managed_path`, and `ready_at` may be null while a staged
upload is being processed. They must all be complete before `status = 'ready'`.
`duplicate` is a terminal audit outcome for a new command whose bytes resolve to
the same media and role's existing active ready variant; its
`validation_data.duplicate_of_variant_id` points to that retained variant and the
new row owns no managed bytes.

### ORM relationships

Add:

```python
Media.variants: Mapped[list[MediaVariant]]
MediaVariant.media: Mapped[Media]
```

Continue using:

```python
Media.asset       # immutable original
Media.derivatives # regenerable previews and proxy
```

Do not overload `Derivative.kind` with `spatial_video`.

## Managed storage

Keep variant bytes separate from immutable originals and regenerable derivatives:

```text
managed/
  originals/<sha-prefix>/<sha>.<extension>
  variants/<media-uuid>/<role>/<sha>.<extension>
  derivatives/<media-uuid>/<recipe-version>/...
```

Variant upload follows the same safety rules as original ingestion:

1. Stream into a random staging path.
2. Enforce configured upload and free-space limits.
3. Hash while reading or in a bounded worker stage.
4. Validate content rather than trusting the filename or submitted MIME type.
5. Flush and atomically move into managed storage.
6. Never overwrite different bytes at an existing managed path.

The external converter must never be allowed to submit an arbitrary server
filesystem path.

## Variant import API

### Command

Add an authenticated machine/browser upload endpoint:

```text
POST /api/v1/media/:media_id/variant-imports
```

Recommended multipart fields:

```text
file                  required
role                  required; spatial_video in this version
converter_name        optional
converter_version     optional
source_asset_sha256   required
```

Requirements:

- Accept bearer API tokens for the Windows pipeline.
- Accept authenticated browser sessions with CSRF protection if a manual upload UI
  is later added.
- `source_asset_sha256` must equal the target `MediaAsset.sha256`. This prevents a
  finished file from being attached to the wrong logical media record.
- Support an `Idempotency-Key` header, or equivalent durable command key.
- Stream large files; do not load them into process memory.
- Return `202 Accepted` with `variant_id` and durable job information.
- Reject image targets and unsupported roles with stable error codes.

Suggested response:

```json
{
  "variant_id": "uuid",
  "media_id": "uuid",
  "role": "spatial_video",
  "status": "staging",
  "job_id": "uuid"
}
```

Suggested error codes:

```text
MEDIA_NOT_FOUND
VARIANT_ROLE_UNSUPPORTED
VARIANT_MEDIA_KIND_UNSUPPORTED
VARIANT_SOURCE_MISMATCH
VARIANT_UPLOAD_TOO_LARGE
VARIANT_DUPLICATE_CONFLICT
VARIANT_INVALID_CONTAINER
VARIANT_INVALID_CODEC
VARIANT_VALIDATOR_UNAVAILABLE
VARIANT_SPATIAL_METADATA_MISSING
VARIANT_DURATION_MISMATCH
VARIANT_STORAGE_FAILED
```

### Durable processing stages

Use the existing durable job/stage-attempt machinery. Recommended stages:

```text
stage_variant_upload
hash_variant
probe_variant
validate_spatial_variant
store_variant
activate_variant
```

The worker does not generate spatial content. It only validates, stores, and
activates the externally generated file.

### Validation

A spatial-video variant must, at minimum:

- Target a `Media.kind == "video"` record.
- Be a supported MP4/QuickTime-family container.
- Contain decodable HEVC/MV-HEVC video.
- Contain the multiview/spatial structures required by the selected Apple playback
  profile.
- Have nonzero dimensions and duration.
- Have duration close enough to the original for intentional paired playback.
- Match `source_asset_sha256`.

Define and test an explicit duration tolerance rather than requiring floating-point
equality. Frame-rate differences may be valid if the converter intentionally
normalizes timing, but the validation result must record them.

The backend's own probe is authoritative. Converter-submitted claims may be stored
as provenance but are untrusted.

The backend image must provide FFmpeg 7.1 or newer with HEVC multiview decoder
options. The production image is pinned to Alpine 3.23 and verifies the required
`view_ids_available` capability while building. The worker also checks the
capability at runtime and reports `VARIANT_VALIDATOR_UNAVAILABLE` rather than
misclassifying a candidate when the decoder is too old or missing.

If stock `ffprobe` in the runtime image cannot expose the Apple spatial structures
needed for a fail-closed check, add a small bounded validator utility or library.
Do not mark a file spatially available merely because it has an HEVC codec name or
`.mov` extension.

Workflow metadata in the variant is optional and must not participate in spatial
validation. Do not create or replace `WorkflowSnapshot` from a variant.

## Atomic activation and replacement

Only `activate_variant` may change the active variant and
`Media.spatial_available`.

For the first valid spatial variant, one transaction must:

1. Lock the target media row.
2. Mark the validated variant `ready` and active.
3. Set `media.spatial_available = true`.
4. Commit.

For replacement:

1. Fully validate and store the new row while the current row remains active.
2. Lock the media and current active variant rows.
3. Deactivate the old row.
4. Mark the new row ready and active.
5. Keep `media.spatial_available = true`.
6. Commit.

Readers must never observe `spatial_available = true` without an active ready
variant. A failed replacement leaves the previous ready variant active.

If the final active spatial variant is administratively invalidated or removed,
set `spatial_available = false` in the same transaction. Do not alter
`prefer_spatial_playback` or `favorite`.

Add a reconciliation operation that recomputes:

```text
media.spatial_available =
    exists(active ready media_variant where role = spatial_video)
```

Run it during migration verification and expose it as an administrative repair
operation or startup audit if appropriate.

## Read API and playback contract

### Media projections

Add these fields to list and detail responses:

```json
{
  "spatial_available": true,
  "prefer_spatial_playback": true
}
```

`spatial_available` is read-only. It is false for image media because it means a
stored spatial-video variant, not the ability of Vision Pro to spatialize an image
at runtime.

The detail response should expose ready active variants:

```json
{
  "variants": [
    {
      "id": "uuid",
      "role": "spatial_video",
      "status": "ready",
      "mime_type": "video/quicktime",
      "byte_size": 123456789,
      "width": 1920,
      "height": 1080,
      "duration_seconds": 8.4,
      "container": "mov",
      "video_codec": "hevc",
      "content_url": "/api/v1/media/<media-id>/variants/<variant-id>/content"
    }
  ]
}
```

Do not expose managed filesystem paths or failed/staging variants in ordinary media
responses.

### Variant content

Add:

```text
GET /api/v1/media/:media_id/variants/:variant_id/content
```

Requirements:

- The variant must belong to the requested media.
- Ordinary clients may retrieve only active, ready variants.
- Use the existing safe managed-path resolver.
- Preserve HTTP range behavior needed by AVFoundation.
- Set the probed content type.

### Preserve existing flat playback

Do not change the meaning of:

```text
GET /api/v1/media/:id/playback
GET /api/v1/media/:id/original
GET /api/v1/media/:id/preview
```

`/playback` continues to select the browser proxy when present and otherwise the
immutable original. It must not silently start returning MV-HEVC because a spatial
variant exists. This keeps the web client and existing integrations stable.

XR will explicitly select the variant content URL after its later backend-contract
update.

## Playback preference API compatibility

The current backend stores `spatial_view_preferred` and rejects video media in
`PUT /api/v1/media/:id/spatial-preference`. The new semantics require the same user
preference for images and videos.

Canonical new contract:

```text
PUT /api/v1/media/:id/playback-preference

{
  "prefer_spatial_playback": true
}
```

The command:

- Accepts both image and video media.
- Is idempotent.
- Changes no availability, variant, workflow, or favorite state.
- May store `true` even while a video variant is unavailable; effective playback
  still falls back to ordinary video.

Compatibility window:

- Keep `PUT /api/v1/media/:id/spatial-preference`.
- Continue accepting `{ "spatial_view_preferred": boolean }`.
- Remove its current image-only validation so an older XR client does not fail on
  video solely because the backend shipped first.
- Return both `prefer_spatial_playback` and the deprecated
  `spatial_view_preferred` alias in media responses during the transition.
- The two response values must always be identical and backed by one database
  column.
- Continue accepting the existing `spatial_view_preferred` list/filter parameter
  as an alias for `prefer_spatial_playback`.
- Reject requests that provide both names with conflicting values.
- Remove legacy names only in a later explicitly coordinated API cleanup after web,
  mobile, and XR clients have migrated.

The existing `favorite` field and endpoint are unchanged. Spatial variant import
must never automatically favorite a media record.

## Migration sequence

Use the next Alembic revision after the repository's current migration head.

Recommended order:

1. Create `media_variant`.
2. Add `media.spatial_available` with non-null false default.
3. Rename `media.spatial_view_preferred` to
   `media.prefer_spatial_playback`, preserving every value.
4. Add indexes and constraints.
5. Run the availability reconciliation query; existing records remain false because
   no variant rows exist yet.
6. Deploy backward-compatible API aliases before updating clients.

No existing `MediaAsset` or `Derivative` rows are copied into `media_variant`.
Originals and proxies retain their current ownership and URLs.

Downgrade must not silently delete imported variant bytes. If the Alembic downgrade
drops the table, document that database rollback requires retaining the managed
variant directory for manual recovery or re-import.

## Service boundaries

Keep variant rules out of route functions. Add a focused service, for example:

```text
comfy_gallery_core/media/variants.py
```

It should own:

- Staged variant creation.
- Hash and duplicate handling.
- Probe and validation orchestration.
- Safe managed placement.
- Atomic activation/replacement.
- Availability reconciliation.
- Read selection of active variants.

Routes should authenticate, validate request shapes, call the service, and project
responses.

The existing original ingestion pipeline should not be generalized prematurely.
Share small file-safety/probe helpers where useful, but keep "create logical media
from original" and "attach variant to existing media" as distinct commands.

## Testing requirements

### Migration

- Existing `spatial_view_preferred` true and false values survive the rename.
- Existing favorite, evaluation, workflow, source, original, and derivative rows are
  unchanged.
- Every preexisting media has `spatial_available = false`.
- Upgrade and downgrade behavior is documented and exercised.

### Model and service

- A ready active spatial variant makes video availability true.
- A staging, processing, failed, inactive, or image-attached variant does not.
- Two concurrent first imports cannot create two active variants.
- Failed replacement leaves the old variant active.
- Successful replacement swaps active rows atomically.
- Duplicate retry with the same idempotency key returns the original result.
- Reconciliation repairs a deliberately corrupted availability projection.
- Variant operations never mutate favorite or playback preference.
- Workflow extraction continues to use only `MediaAsset`.

### API

- Valid machine-token upload returns `202`.
- Source SHA mismatch and image targets fail with stable codes.
- Invalid HEVC, ordinary mono HEVC, and missing spatial metadata fail closed.
- Media list/detail expose availability and canonical preference.
- Detail exposes only active ready variants.
- Variant content enforces ownership and safe path resolution.
- Byte ranges work for variant content.
- Existing `/playback`, `/original`, and `/preview` behavior is unchanged.
- Canonical and compatibility preference endpoints update the same stored value.
- Video preference updates no longer return
  `SPATIAL_PREFERENCE_UNSUPPORTED`.
- Old and new filter parameter names resolve to the same query.

### Integration fixture

Add a small legal-to-store spatial MV-HEVC fixture to the private test corpus. Record:

- Original/source SHA-256.
- Expected duration and dimensions.
- Expected spatial validation facts.
- Expected HTTP range result.

Also keep negative fixtures for ordinary HEVC and corrupt/missing spatial metadata.
Do not make the full CI suite depend on running the expensive spatial conversion
pipeline.

The first private positive fixture was exercised on 2026-07-29 using the output of
Apple's `ConvertingSideBySide3DVideoToMultiviewHEVCAndSpatialVideo` example:

```text
source SHA-256:
83716e08b2d550a3e25617e7ce84f2bc50b94f8cc1dae94850ab5339e21bab68

spatial variant SHA-256:
3c43371922649419942ae0c637003e31992ae631d52c697569a5d8c99f19c376

source:
3840x1080, 30 fps, 4.333333 seconds, HEVC side-by-side

spatial variant:
1920x1080, 30 fps, 4.333333 seconds, multilayer HEVC
```

FFmpeg exposes Apple stereo metadata with a 64,000 micrometer baseline,
`80000/1000` horizontal field of view, and `primary_eye=none`. `none` is valid
for this Apple-produced file; validation therefore requires the field to be
present and recognized but does not require a left/right primary eye. Both
`vidx:0` and `vidx:1` decode successfully. The complete local API/worker import
reached active `ready`, set `spatial_available=true`, preserved ordinary playback,
and returned a correct 1,024-byte HTTP range with `206 Partial Content`.

The ignored private regression is enabled with:

```bash
CG_PRIVATE_SPATIAL_SOURCE=/path/to/Hummingbird.mov \
CG_PRIVATE_SPATIAL_VARIANT=/path/to/Hummingbird_Spatial.mov \
uv run pytest tests/golden/test_private_spatial_video_fixture.py
```

## Documentation updates required with implementation

The implementing main-session agent must update the governing documents in the same
change:

- `doc/product/requirements.md`
  - Add requirements for alternate video variants, system-owned spatial
    availability, externally imported spatial validation, and shared image/video
    playback preference.
- `doc/architecture/data-model.md`
  - Add `MEDIA_VARIANT`, change the media relationship diagram, and document the
    availability projection.
- `doc/design/media-ingestion.md`
  - Add the variant-import pipeline, managed variant layout, validation, and
    replacement invariants.
- `doc/interfaces/api-and-integrations.md`
  - Add variant import/content and canonical preference contracts, plus the
    compatibility window.
- `doc/requirements-traceability.md`
  - Map the new requirements to migration, service, API, and tests.
- Add an ADR because this changes the previous one-original-plus-regenerable-
  derivatives file ownership boundary.

Suggested requirement IDs, if still unused at implementation time:

```text
MEDIA-010  One logical video may own validated alternate playable variants.
MEDIA-011  Spatial availability is system-owned and derived from an active ready
           spatial-video variant.
ING-015    External spatial variants are durably staged, validated, and atomically
           activated without replacing the original.
LIB-016    Spatial playback preference applies independently to image and video,
           with ordinary playback fallback when unavailable.
```

## Implementation checklist

- [x] Add and verify the Alembic migration.
- [x] Add `MediaVariant` ORM model and relationships.
- [x] Add the variant service and safe managed storage layout.
- [x] Add durable import job/stages.
- [x] Add fail-closed spatial MV-HEVC validation.
- [x] Add machine-token multipart variant import.
- [x] Add variant projections and range-capable content delivery.
- [x] Add `spatial_available` to media projections and filtering.
- [x] Add the canonical shared playback-preference command.
- [x] Preserve the old preference field, endpoint, and filter aliases temporarily.
- [x] Keep original/proxy playback behavior unchanged.
- [x] Add migration, service, API, idempotency, replacement, reconciliation, and
      synthetic validation tests.
- [x] Update requirements, architecture, design, API, traceability, and ADR docs.
- [x] Export and regression-test the OpenAPI contract.
- [x] Add an optional private real MV-HEVC regression and verify it with FFmpeg
      8.1 plus the local API/worker.
- [ ] Repeat the real fixture against the packaged Linux/amd64 backend image and
      deployed reverse proxy.
- [x] Run `make check` after the final implementation change (91 Python passing,
      one optional private-fixture test skipped by default, and 20 frontend tests
      passing on 2026-07-29).
- [ ] Verify an actual spatial file on the deployed backend and Vision Pro before
      removing any compatibility alias.

## Backend completion boundary

The backend update is complete when:

1. An external Windows pipeline can attach a validated spatial MV-HEVC file to an
   existing video using a bearer token and the original SHA-256.
2. The original remains immutable and remains the flat web/iOS playback source.
3. The same media detail exposes the active spatial variant to a capable client.
4. `spatial_available` accurately reflects the active ready video variant.
5. One user preference controls intended spatial playback for both image and video.
6. Existing XR, web, and mobile clients continue to work during the compatibility
   window.
7. No backend code attempts ml-sharp, SBS generation, MV-HEVC encoding, or spatial
   image conversion.
