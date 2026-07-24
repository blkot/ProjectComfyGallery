# Phase 6 NAS Release and Verification

**Status:** Complete and verified on 2026-07-24

**Locked release:** `0.1.0-rc.5`

## Delivered release slice

Phase 6 turns the existing application into an operational NAS release:

- `compose.production.yaml` removes PostgreSQL and Redis host ports while retaining
  the LAN-facing web port.
- Every service has bounded CPU/memory defaults and rotated JSON logs.
- The worker remains one process and one thread; media hashing, decoding, and video
  transcoding cannot fan out on the J4125.
- The worker emits an atomic heartbeat and the API requeues stale durable jobs from
  PostgreSQL after API startup.
- A scheduled backup service creates PostgreSQL custom-format dumps, validates them
  with `pg_restore --list`, records SHA-256 and the Alembic version, and retains seven
  daily and four weekly copies by default.
- Restore requires an exact database-specific confirmation value and validates both
  the checksum and archive before replacing its target database.
- Portable export requests run through the durable maintenance queue and produce
  authenticated ZIP downloads with table-shaped JSON Lines, CSV score/analysis
  summaries, stable IDs, a checksummed manifest, and no password/session/token
  material.
- The Operations page reports database, broker, worker freshness, durable jobs,
  managed/staging/export disk pressure, backup freshness, and recent scan/sync/export
  activity.
- Login failures receive bounded in-process rate limiting. Nginx adds CSP,
  clickjacking, MIME-sniffing, referrer, and permissions headers.
- Runtime images upgrade distribution packages during the build. The API/worker uses
  Alpine with FFmpeg 8, avoiding the unfixed Debian multimedia advisories found
  during the release audit.

Migration `0007_nas_release_operations` adds the durable `export_run` record. Export
artifacts live on the mounted filesystem and remain independently deletable or
backable up without changing relational history.

## Automated verification

The final local gate:

- Ruff lint and formatting: pass.
- strict mypy: pass across 63 application modules.
- pytest: 52 tests pass.
- frontend TypeScript/ESLint: pass.
- frontend Vitest: 10 tests pass.
- Python and production JavaScript dependency audits: no known vulnerabilities.
- Trivy 0.72 source scan: no committed secret findings.
- Trivy 0.72 scan of all five final amd64 production image artifacts: zero critical
  and zero high findings.
- development and production Compose rendering: pass.
- clean PostgreSQL migration `0001` through `0007`: pass.
- Alembic schema-drift check after restore: pass.
- Final hardened-image smoke run: all 14 golden files imported (six images and eight
  videos) with zero failures, while API, worker, and scheduled backup remained
  healthy.

Phase 6 regressions cover:

- Portable export contents, schema manifest, workflow-evidence opt-out, and
  path-containment.
- Password hashes and API-token material absent from exports.
- Fresh/stale worker heartbeat behavior.
- Persistent failed and overdue backup status.
- Interrupted stale jobs requeued while fresh running jobs are not duplicated.
- Low-disk safety-reserve rejection.
- Login rate-limit expiry and successful-login reset.

## Recovery rehearsal

A disposable local production stack completed the following:

1. Migrated an empty PostgreSQL database through `0007`.
2. Created and validated a 166,711-byte custom-format scheduled dump.
3. Restored that dump into `comfygallery_restore`.
4. Verified the administrator, 11 criteria, four templates, and migration head.
5. Ran Alembic schema-drift detection against the restored database.

The same guarded restore was then repeated on the real amd64 NAS. The restored
database reported migration `0007`, one administrator, and all 11 criteria.

## Real J4125 NAS evidence

Target:

- Intel Celeron J4125, amd64.
- 8 GB RAM.
- Docker 27.1.2 and Compose 2.29.1.
- Existing main filesystem at 97% usage; approximately 133 GB remained before the
  rehearsal.

A private, disposable validation stack used the 14-file golden corpus plus 1,008
hard-linked duplicate paths. This exercised traversal and hashing without consuming
another 1.5 GB of media storage.

First pass:

- 1,036 candidate paths discovered.
- 14 unique media imported and fully processed.
- 481 exact duplicates resolved before the permission fix completed.
- 527 owner-only files produced durable `MEDIA_COPY_FAILED` records.
- 14 macOS sidecar files produced `MEDIA_UNSUPPORTED_FORMAT` without blocking the
  batch.
- Completed in 196.2 seconds.
- API/review/status p95 latency: 93.0 ms; worst observed request: 317.6 ms.

After making the disposable source readable, a manual rescan recovered every prior
permission failure:

- 527 exact duplicates resolved.
- 495 unchanged paths skipped without rehashing.
- 14 intentionally unsupported sidecars remained isolated errors.
- Completed in 148.2 seconds.
- Worst observed review/status request: 135.6 ms.

While the worker was stopped, a portable export remained queued. Restarting the
worker completed the same job, demonstrating durable broker/worker recovery. The
real-NAS export then completed in 2.1 seconds:

- 14 media rows.
- 14 workflow snapshots.
- 24 non-empty exported tables/summaries.
- 790,999-byte ZIP.
- Downloaded SHA-256 matched the recorded artifact hash.

The authenticated system status correctly reported healthy database, Redis, worker,
jobs, backup, and recent activity while retaining warnings for the real 97% disk
usage.

## Cleanup

Both disposable Compose projects, their named volumes, validation images, copied
source/media/backups, and temporary restored databases were removed. Existing NAS
containers and user media were not modified.

## Operational decisions confirmed

- NAS source files must be readable by container UID 10001; they do not need to be
  writable.
- Database dumps protect relational/manual work. Managed originals still require the
  operator's normal NAS snapshot/backup policy.
- Portable exports are for data portability and inspection, not database disaster
  recovery.
- Actual disk percentage should remain a warning even when absolute free bytes still
  exceed the placement reserve.
- CPU ffmpeg is the release default. Intel `/dev/dri` acceleration remains optional
  future tuning because the bounded CPU path met the MVP responsiveness gate.
