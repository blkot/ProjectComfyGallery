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
4. The worker streams `MediaAsset`'s immutable original to MSS
   `POST /spatial/batches` with `publish_to_gallery=true`.
5. It persists `batch_id`, then polls
   `GET /spatial/batches/{batch_id}`. It never follows the returned `status_url`.
6. MSS converts on its GPU host and calls CG's existing authenticated
   `/variant-imports` flow.
7. CG validates and activates the result. The orchestration worker requires MSS
   publish success and independently observes the active ready variant for the
   same `media_id` before marking its run and job succeeded.
8. The client polling the CG run invalidates Media Detail and displays the new
   variant. Closing the page does not affect the run.

## Production configuration

Set on the ComfyGallery host:

```dotenv
CG_MSS_BASE_URL=http://<mss-host>:8000
CG_MSS_API_TOKEN=
CG_MSS_HTTP_TIMEOUT_SECONDS=600
CG_MSS_POLL_INTERVAL_SECONDS=5
CG_MSS_MAX_POLL_SECONDS=21600
CG_MSS_PUBLISH_GRACE_SECONDS=120
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
- Once `mss_batch_id` is committed, retry and startup recovery resume polling that
  batch rather than resubmitting the source.
- Each poll refreshes the run timestamp. Generic startup recovery treats recent
  run activity as liveness and requeues the job only after that activity is stale.
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

Stable CG run errors include:

- `MSS_SUBMIT_FAILED`: source upload or MSS submit request failed.
- `MSS_STATUS_FAILED`: the persisted batch could not be polled.
- `MSS_RESPONSE_INVALID`: MSS response lacks required structure.
- `MSS_POLL_TIMEOUT`: batch exceeded the configured watch duration.
- `MSS_PUBLISH_FAILED`: MSS terminal item did not publish.
- `MSS_MEDIA_MISMATCH`: MSS reported publishing to another media UUID.
- `MSS_PUBLISH_NOT_OBSERVED`: MSS claimed success but CG did not observe its ready
  active variant during the grace period.

All failures preserve the immutable original and any existing ready spatial
variant. Retryable failed jobs can use the normal Jobs retry endpoint; if a batch
ID exists, retry continues that batch.

## Validation checklist

Before production enablement:

1. Apply migration `0013_spatial_conversion_runs` and start `worker-spatial`.
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
