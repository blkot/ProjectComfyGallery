# Backup, Recovery, and Observability

**Status:** Implemented for the MVP NAS release

## Recovery priorities

Order of irreplaceability:

1. Manual evaluation scores and revisions.
2. Criterion/templates and weighting profiles.
3. Manual node/model registry corrections.
4. Saved analysis runs and collections/tags.
5. Managed original media.
6. Imported non-regenerable media variants.
7. Regenerable semantic extractions.
8. Regenerable thumbnails/proxies.

Source rescanning cannot recreate manual work.

## Backup scope

### PostgreSQL

Automatic logical backups include:

- Authentication and API-token records.
- Media/source inventory.
- Raw embedded metadata stored in PostgreSQL.
- Generic/semantic workflow records.
- Node/model registries.
- Evaluations and revisions.
- Collections, filters, review sessions.
- Analysis runs and results.
- Job history required for recovery.

### Managed media

Managed original media and imported variants are backed up through the NAS/storage
backup strategy. Variants are not regenerable by the NAS worker, so both
`managed/originals` and `managed/variants` must be included. The application
documents expected paths but does not duplicate media into database backups.

### Derivatives

Thumbnail/proxy backup is optional because derivatives are regenerable.

### Configuration

Deployment configuration, source-root mappings, and secrets must have a secure operator backup. Secrets should not be included in portable user exports.

## Default retention

- Seven daily PostgreSQL dumps.
- Four weekly PostgreSQL dumps.

Retention is configurable.

**Proposed recovery objectives:**

- Database RPO: at most 24 hours under default daily backup.
- Service RTO: same day for a practiced restore on the NAS.

These objectives are operational targets rather than cloud-service guarantees.

The scheduled `backup` Compose service runs once after the API becomes healthy and
then every `CG_BACKUP_INTERVAL_SECONDS` (24 hours by default). A successful Sunday
UTC backup is also copied into weekly retention.

```dotenv
BACKUP_ROOT=/share/ComfyGallery/backups
CG_BACKUP_INTERVAL_SECONDS=86400
CG_BACKUP_DAILY_KEEP=7
CG_BACKUP_WEEKLY_KEEP=4
CG_BACKUP_EXPECTED_INTERVAL_HOURS=30
```

Backup files are private application data and are created with UID/GID 10001 and
group-restricted permissions. The status API reads `.backup-status.json`; a failure
remains visible until a later backup succeeds.

## Backup procedure

1. Run `pg_dump` in a consistent custom format.
2. Write to a temporary backup path.
3. Validate command success and non-zero output.
4. Record database/application schema versions and timestamp in a manifest.
5. Atomically move backup and manifest into retention storage.
6. Optionally calculate SHA-256.
7. Apply retention only after a new backup succeeds.
8. Emit structured success/failure status.

Backup failure must remain visible in system status until a later successful backup.

### Manual backup command

```bash
docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps backup run
```

List available backup IDs without changing host permissions:

```bash
docker compose -f compose.yaml -f compose.production.yaml \
  exec backup sh -c 'ls -1 /backups/daily; ls -1 /backups/weekly'
```

Each backup directory contains `database.dump`, `database.dump.sha256`, and
`manifest.json`. The manifest records the backup ID, completion time, database,
Alembic version, checksum, and byte size.

The service does not copy managed media. Include `MEDIA_DATA_ROOT` and `BACKUP_ROOT`
in the NAS's normal snapshot/off-device backup policy.

## Restore procedure

High-level restore:

1. Stop API, worker, and scheduled backup writes.
2. Preserve the failed/current database volume for investigation.
3. Start an empty compatible PostgreSQL instance.
4. Verify backup manifest and checksum.
5. Restore the dump.
6. Run required forward migrations using the intended application release.
7. Start API in readiness-check mode.
8. Verify counts and representative data:
   - users/login,
   - media and assets,
   - raw workflow snapshots,
   - model/node corrections,
   - criteria/scores/revisions,
   - saved analyses.
9. Reconcile managed original/variant paths, spatial availability, and missing derivatives.
10. Start workers and regenerate derivatives/requeue incomplete jobs.

### Production restore commands

Assume the target is `comfygallery` and the backup is
`cg-YYYYMMDDTHHMMSSZ`:

```bash
docker compose -f compose.yaml -f compose.production.yaml \
  stop api worker backup

docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps \
  -e CG_RESTORE_CONFIRM=restore:comfygallery \
  backup restore /backups/daily/cg-YYYYMMDDTHHMMSSZ

docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini upgrade head

docker compose -f compose.yaml -f compose.production.yaml \
  start api worker backup
```

The restore rejects paths outside `CG_BACKUP_ROOT`, requires the exact
`restore:<target database>` confirmation, validates the checksum and
`pg_restore --list`, and restores with `--exit-on-error`.

Before production restore, preserve the current PostgreSQL volume or take a NAS
snapshot. Rehearse into a disposable database by overriding `PGDATABASE` and using
the matching confirmation; never rehearse by replacing live data.

## Restore testing

- CI tests schema migration on seeded historical database fixtures.
- A release candidate should restore the latest representative backup into a disposable database.
- Production operators should periodically perform a test restore without replacing the live database.
- A backup is not considered trustworthy solely because `pg_dump` returned success.

## Portable exports

The application supports user-requested exports of:

- Evaluation templates and criteria.
- Current scores and revision history.
- Media UUID/SHA/provenance references.
- Model registry and series.
- Node semantic mappings.
- Collections/tags/saved filters.
- Saved analysis definitions/results.

Formats:

- JSON for lossless structured portability.
- CSV for evaluation/analysis inspection where the data is naturally tabular.

Exports:

- Use stable IDs.
- Record export schema version.
- Never replace database backup as the primary recovery format.
- Exclude password/session/token secrets.

Implemented bundle/API:

- `POST /api/v1/exports` queues a durable maintenance job.
- `GET /api/v1/exports` and `GET /api/v1/exports/:id` show progress/history.
- `GET /api/v1/exports/:id/download` serves the authenticated ZIP.
- `manifest.json` records schema/application versions, stable ID, counts, inner-file
  byte sizes, and SHA-256 values.
- JSON Lines preserve stable IDs/history; CSV summarizes evaluation scores and
  analysis results.

Password hashes, sessions, tokens, and transient worker/upload state are excluded.
Prompts, workflow metadata, filenames, and source paths can still be private, so the
bundle requires the same protection as the library.

## Observability goals

The user should answer:

- Is the application healthy?
- Is the worker processing?
- Is disk space sufficient?
- Which import is progressing or stuck?
- Which stage failed and can it be retried?
- Is ComfyUI/LoRA Manager synchronization degraded?
- When was the last successful backup?

## Structured logging

Every service logs:

- Timestamp.
- Severity.
- Service/component.
- Request/job ID.
- Media/batch ID where relevant.
- Stable event/error code.
- Human-readable message.

Logs must not contain:

- Passwords.
- Session cookies.
- API token values.
- Full prompts by default.
- Entire workflow/provider payloads by default.

## Job observability

PostgreSQL owns:

- Job state.
- Stage attempts.
- Progress counters.
- Retry history.
- Structured error.
- Cancellation request.

Redis/broker metrics are supplemental.

Stuck-job reconciliation:

- Detect in-progress leases/heartbeats older than a configured threshold.
- Mark attempt interrupted.
- Requeue retryable stages.
- Avoid duplicating completed idempotent stages.

## Health checks

### Liveness

Confirms the process is responsive. It should not fail simply because an optional external integration is unavailable.

### Readiness

Confirms:

- Database reachable and schema compatible.
- Required managed/staging paths accessible.
- API can serve requests.

Worker readiness additionally checks broker/database and required filesystem access.

### System status

Authenticated status page includes:

- API/worker/database/broker state.
- Queue counts.
- Active/failed jobs.
- Free disk space for managed/staging/backup paths.
- Last source scans.
- Last node/model sync.
- Last successful backup.
- Optional integration degradation.

The implemented status also includes atomic worker-heartbeat age/version, durable
queue and stuck-running counts, managed/staging/export filesystem usage, persisted
backup age/result, and the latest scan, registry sync, and export. A high filesystem
use percentage remains a warning even when free bytes exceed the placement reserve.

## Metrics

Metrics may initially be exposed through the authenticated status API rather than a full monitoring stack.

Useful metrics:

- Imports by result and stage.
- Stage duration percentiles.
- Queue depth and oldest age.
- Worker heartbeats.
- Processing/retry failure counts.
- Thumbnail/proxy throughput.
- Database connection/pool state.
- Disk free bytes.
- Backup age/duration/size.
- Registry sync outcomes.

Prometheus integration is **Deferred** unless the deployment environment already uses it.

## Alerts

Built-in notification integrations are **Deferred**. Persistent status warnings are required for:

- No successful backup within the expected interval.
- Critically low disk space.
- Repeated worker crash/stuck jobs.
- Database schema mismatch.
