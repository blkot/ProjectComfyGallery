# Phase 1 Media Ingestion and Verification

**Status:** Implemented and verified on 2026-07-23
**Release:** `0.1.0-rc.4`

## Outcome

Phase 1 delivers the first complete product slice: authenticated media enters through
the browser or a manually scanned read-only NAS mount, receives stable content
identity, is preserved as an immutable original, is made browser-viewable, and is
manageable through the frontend. ComfyUI workflow extraction intentionally begins in
Phase 2.

## Implemented architecture

### Identity and records

- `Media.id` is application-generated UUIDv7 and never derives from a filename,
  source path, or ComfyUI instance.
- `MediaAsset.sha256` is the unique exact-byte identity.
- `SourceOccurrence` retains each root/relative-path observation, its size, mtime,
  hash, current state, scan links, errors, and superseded history.
- `Derivative` stores versioned thumbnails, video posters, and video proxies.
- `UploadBatch`/`UploadItem` and `ScanBatch` retain user-visible batch outcomes.
- `Job` and `JobStageAttempt` retain status, progress, stage, attempt, cancellation,
  structured error, and retryability.

The schema is introduced by Alembic revision `0002_media_ingestion`.

### Storage safety

Originals use:

```text
managed/originals/<sha256-prefix>/<sha256>.<detected-normalized-extension>
```

The original location and owning database records are committed before the final
atomic move. A redelivered job handles each interruption boundary:

1. Before database commit: staging still exists and normal ingestion restarts.
2. After database commit but before placement: the existing asset record directs the
   retry to complete placement from staging.
3. After placement: the upload item already links the media and processing resumes
   from the immutable original.

No endpoint physically deletes managed originals.

### Browser upload

`POST /api/v1/media/imports`:

- Requires an authenticated session or bearer principal and CSRF for session writes.
- Accepts up to 200 multipart files per batch.
- Streams each file to randomized staging without loading it into memory.
- Enforces the configured per-file size limit.
- Creates durable items/jobs before enqueueing worker processing.

### NAS scan

Source roots:

- Must resolve under `CG_ALLOWED_SOURCE_ROOTS`.
- Must not overlap managed or staging storage.
- Are mounted read-only in the production Compose file.
- Never follow symlinks.

One scan actor streams recursive directory iteration and processes each supported
candidate sequentially. It does not build a full file list or fan thousands of item
messages into Redis. Path/size/mtime unchanged records skip hashing. Changed bytes
create a new source-occurrence version; renamed exact bytes link the existing media;
unseen prior occurrences become missing without deleting managed media.

NAS scans explicitly opt out of Dramatiq's ten-minute default actor limit because
sequential processing on the target J4125 can legitimately run for hours. This
prevents automatic actor retries from replaying an in-progress batch. An operator
can set `CG_SCAN_ACTOR_TIME_LIMIT_SECONDS` to a nonzero deployment-specific limit;
the production default is `0` (unlimited).

### Media processing

Supported content is identified by file signature and verified by Pillow/FFprobe:

- PNG, JPEG, WebP.
- MP4, WebM.

Stored facts include detected format, MIME, dimensions, duration, frame rate,
container, video codec, audio codec, and raw probe output. Images receive a versioned
WebP thumbnail. Videos receive a representative JPEG poster. Browser-incompatible
video receives a versioned H.264/AAC MP4 proxy while retaining the original.

The production worker is fixed at one process and one thread for the J4125. FFmpeg
uses CPU fallback and requires no CUDA.

### HTTP and frontend

Implemented pages:

- Media Library with type/status filters and bounded pagination.
- Imports with browser upload, source-root registration, rescan controls, and batch
  histories.
- Jobs with status filtering, stage/progress/error visibility, retry, and cooperative
  cancel.
- Media Detail with image/original display, proxy video playback, original download,
  identity facts, derivatives, and source history.

Media responses require authentication. Video delivery supports byte ranges through
Starlette `FileResponse` and Nginx.

## Automated verification

Backend:

```text
ruff: passed
mypy --strict: passed
pytest: 12 passed
```

Coverage includes:

- Signature detection independent of extension.
- Probe/hash/thumbnail generation.
- Unsupported-byte rejection.
- Exact duplicate collapse to one immutable original.
- Same-name/different-content scan behavior.
- Unchanged rescan skipping.
- Rename/missing tracking.
- Changed-path occurrence versioning.
- Retry after the database-committed/pre-placement interruption boundary.

Frontend:

```text
eslint + TypeScript: passed
Vitest: 4 passed
Vite production build: passed
```

The API client test suite verifies CSRF behavior, stable error envelopes, and that
multipart requests leave `Content-Type` boundary construction to the browser.

## Production-stack verification

A fresh Docker Compose database was migrated to `0002_media_ingestion`; `alembic
check` reported no schema drift. PostgreSQL, Redis, API, worker, and web health checks
passed.

The disposable corpus exercised:

- Browser upload of PNG and HEVC MP4.
- HEVC probe plus JPEG poster and H.264 proxy generation.
- HTTP `206 Partial Content` playback of the proxy.
- Upload-to-source and source-to-source exact deduplication.
- Same filename with different content.
- Fully unchanged rescan.
- Rename plus in-place changed content.
- Missing old path and retained source history.
- Corrupt `.png` isolation as `MEDIA_UNSUPPORTED_FORMAT` while the batch completed
  with errors.
- Duplicate upload after API/worker container replacement.
- UUIDv7 values on every resulting media record.
- Recursive scan pruning of NAS/system metadata directories, including a regression
  for QNAP `.@__thumb` variants that otherwise appear as valid PNG media.

The React application was then tested through a real browser session: login,
dashboard counts, library filtering, media cards/previews, video detail readiness,
import history, and job/error history all passed without application console errors.

Production images were built for `linux/amd64`, the target architecture of the J4125
NAS.

## Known limits and next phase

- Browser transfer is multipart, not resumable.
- Scan work is cancelable between files, not within a file/FFmpeg subprocess.
- Thousands-file memory behavior follows a streaming implementation and bounded
  worker, but the final J4125 scale/timing run belongs to Phase 6 with the private
  corpus.
- Proxy settings are recipe-versioned and may be tuned after representative videos
  are supplied.
- Embedded workflow evidence, node graphs, prompts, semantic extraction, and node/model
  registries are Phase 2/3 work.

## Phase 2 corpus handoff

This handoff was completed during Phase 2. The supplied 6-image/8-video private corpus
is organized under stable hash-derived case IDs and verified in
[Phase 2 workflow evidence](phase-2-workflow-evidence.md). Future additions follow
[Testing and golden corpus](testing-and-golden-corpus.md).
