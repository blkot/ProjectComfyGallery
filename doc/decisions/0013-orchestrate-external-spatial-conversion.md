# ADR-0013: Orchestrate External Spatial Conversion

**Status:** Accepted
**Date:** 2026-08-10

## Context

ComfyGallery owns the canonical ordinary video and already accepts an externally
generated Apple spatial MOV as a validated variant. ml-sharp-spatial (MSS) can
perform the GPU conversion and publish that result back. Requiring the user to
leave Media Detail, start MSS manually, and later attach or rediscover the result
breaks the desired one-action workflow.

The NAS has no suitable GPU. Browser-to-MSS calls would expose service topology
and credentials, disappear with the page, and make restart recovery unreliable.
The conversion may run for hours and must not block ordinary media or workflow
queues.

## Decision

- ComfyGallery is the orchestration authority; MSS remains the conversion and
  publication executor.
- The browser calls only authenticated ComfyGallery endpoints.
- Each command creates a durable `SpatialConversionRun` and ordinary `Job`.
  One active run is allowed per media; repeated commands return it.
- A dedicated one-process/one-thread `spatial` worker pushes the immutable
  original to `POST /spatial/batches`, polls the batch endpoint, and stores
  bounded status evidence.
- Status polling reconstructs the path from the configured MSS origin and
  returned batch ID; it never follows an arbitrary returned status URL.
- The run succeeds only when MSS reports `published` or `variant_exists` and CG
  observes an active ready variant for the same media.
- Conversion failure never modifies the immutable original or deactivates a
  prior ready variant. MSS continues to publish through the existing validated,
  idempotent variant-import contract.
- MSS configuration and credentials are server-only environment settings. A
  blank base URL disables the feature cleanly.

## Consequences

- The user can leave or close Media Detail; PostgreSQL and the worker retain the
  operation state.
- Worker and API restarts resume a persisted MSS batch. The polling loop updates
  the run timestamp so generic startup reconciliation does not duplicate a live
  watcher.
- A crash after MSS accepts a submission but before its batch ID is committed can
  still resubmit work because the current MSS submit API has no command-key
  contract. Adding submission idempotency to MSS would close this narrow window.
- Pushing large originals occupies a spatial worker connection but does not load
  the entire file into memory or consume the NAS media/background worker slots.
- A future MSS callback may replace polling without changing the run or media
  variant domains.

## Alternatives considered

- **Browser calls MSS directly:** rejected because state and credentials would be
  client-owned and the task would not survive navigation or browser closure.
- **Run conversion on the NAS:** rejected because the J4125 host has no CUDA GPU
  and CG should not own MSS implementation details.
- **Treat the conversion run as a variant:** rejected because an attempt owns no
  validated alternate bytes and may fail before a variant exists.
- **Use the existing background queue:** rejected because long polling would
  block workflow, scan, registry, and maintenance work on its single thread.
