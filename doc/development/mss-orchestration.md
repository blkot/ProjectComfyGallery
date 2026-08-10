# MSS Orchestration Implementation and Operations

**Status:** Implemented; live MSS/NAS validation pending

**Date:** 2026-08-10

## Goal and boundary

From a normal video Media Detail page, the user can start ml-sharp-spatial (MSS)
and later see the spatial variant on that same logical media. The browser talks
only to ComfyGallery. The NAS does not perform GPU conversion. MSS publishes the
result through the existing variant-import API, so all MV-HEVC validation and
atomic activation rules remain unchanged.

## End-to-end sequence

1. The client reads
   `GET /api/v1/media/{media_id}/spatial-conversions/current`.
2. The user invokes
   `POST /api/v1/media/{media_id}/spatial-conversions`.
3. CG creates `spatial_conversion_run` plus a standard `job` and enqueues the
   dedicated `spatial` worker. A concurrent active request is returned instead of
   duplicated.
4. The finite submission worker streams `MediaAsset`'s immutable original to MSS
   `POST /spatial/batches` with `source_media_id`, `publish_to_gallery=true`, and
   `cleanup_mode=delete_all`, then persists `batch_id` and completes the local Job.
5. A separate low-frequency or on-demand actor performs exactly one origin-pinned
   `GET /spatial/batches/{batch_id}` and returns; it never follows `status_url`.
6. MSS converts on its GPU host and calls CG's existing authenticated
   `/variant-imports` flow.
7. CG validates and activates the result. This activation/duplicate event is the
   success authority; reconciliation can recover a missed event only by observing
   a matching active ready variant.
8. The client can refresh status on demand and displays publish-only retry state.

## Production configuration

Set on the ComfyGallery host:

```dotenv
CG_MSS_BASE_URL=http://<mss-host>:8000
CG_MSS_API_TOKEN=
CG_MSS_HTTP_TIMEOUT_SECONDS=600
CG_MSS_RECONCILIATION_INTERVAL_SECONDS=300
CG_MSS_CONVERTER_NAME=ml-sharp-spatial
CG_MSS_CONVERTER_VERSION=0.1
```

`CG_MSS_API_TOKEN` authenticates CG to MSS only if MSS protects its API. MSS must
separately have the ComfyGallery base URL and CG-issued bearer token needed to
publish variants. Do not put either token in frontend configuration.

The Compose deployment includes `worker-spatial`. It shares the backend image and
managed media volume but consumes only the `spatial` queue. A blank
`CG_MSS_BASE_URL` leaves the API and UI available while disabling the start action.

## Recovery and idempotency

- PostgreSQL, not Redis or the page, is authoritative for a conversion run.
- Once `mss_batch_id` is committed, retry and startup recovery reconcile that
  batch rather than resubmitting the source; rc.19's old running submit Job is
  completed during recovery.
- A reconciliation actor makes one GET and uses persisted throttle state to avoid
  multiplied watchers; transient status errors schedule another low-frequency run.
- Only one queued/submitting/processing run may exist for a media. A terminal run
  is retained and a new command creates a new run.
- Each MSS publication must use an idempotency key stable for that conversion run,
  not a permanent key based only on media ID. A permanent media key would return an
  old variant when deliberately reconverting.
- MSS currently has no submission-command idempotency contract. A crash in the
  narrow interval after MSS accepts the upload but before CG commits `batch_id`
  can submit duplicate converter work. The database and variant-import contracts
  still prevent duplicate CG media/variant activation.

## Failure semantics

CG error handling distinguishes command failures from reconciliation evidence:

- `MSS_SUBMIT_FAILED`: source upload or MSS submit request failed.
- `MSS_STATUS_FAILED`: a transient reconciliation GET failed. This is logged and
  rescheduled at the low-frequency interval; it does not make the run or the
  already-completed submission Job fail.
- `MSS_RESPONSE_INVALID`: an invalid submission response fails the submission
  command; an invalid status response is transient and rescheduled like
  `MSS_STATUS_FAILED`.
- `MSS_GENERATION_FAILED`: MSS generation failed.
- `MSS_PUBLISH_FAILED` / `MSS_PUBLISH_SKIPPED`: MSS retains a result that can be
  retried through publish-only retry.

All failures preserve the immutable original and any existing ready spatial
variant. The normal Jobs retry endpoint applies only when the finite submission
Job failed before CG persisted a batch ID. Once a batch ID exists, that Job is
already succeeded: status-read failures reschedule reconciliation, generation
failure requires a new conversion run, and failed/skipped publication uses the
publish-only retry endpoint. Ordinary Job retry never resumes or resubmits a
persisted MSS batch.

## Validation checklist

Before production enablement:

1. Apply migrations through `0014_event_driven_mss` and start `worker-spatial`.
2. Confirm the NAS container can reach MSS's base URL.
3. Confirm MSS can authenticate back to CG and its CG URL is reachable.
4. Choose a ready, ordinary video and start conversion from Media Detail.
5. Leave the page, return, and confirm queued/processing state is restored.
6. Let MSS finish; confirm the run succeeds, `spatial_available=true`, and Media
   Detail shows the active `ml-sharp-spatial` variant.
7. Stop/restart `worker-spatial` during a test batch and confirm it resumes using
   the same MSS batch ID.
8. Exercise one MSS failure and confirm the CG original/prior variant is unchanged
   and the stable error is visible.
# MSS event-driven operation

The spatial conversion Job is only a finite submission command. It posts one video
to MSS with `source_media_id`, `publish_to_gallery=true`, `cleanup_mode=delete_all`,
and configured converter options, then stores `mss_batch_id` and completes. Never
submit again once a batch ID exists. MSS owns GPU queueing and publishes variants
back through CG. CG marks a run successful only when its own validated activation
or duplicate resolution observes the active ready variant.

`reconcile_spatial_conversion` makes exactly one origin-pinned MSS status GET and
returns. It is scheduled at `CG_MSS_RECONCILIATION_INTERVAL_SECONDS` (default 300)
and by Detail's Refresh action; it is recovery/progress evidence, not lifecycle
authority. For MSS `publish_status=failed|skipped`, use retry publication; this
calls MSS `/spatial/batches/{id}/publish` without GPU resubmission. rc.19 rows with
a batch finish their old Job and reconcile; rows without a batch may resubmit.
