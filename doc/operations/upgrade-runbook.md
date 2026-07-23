# Upgrade Runbook

**Status:** Implemented operational procedure

## Before maintenance

1. Review release notes and migrations.
2. Confirm Operations reports a healthy database, broker, and worker.
3. Create a fresh database backup:

   ```bash
   docker compose -f compose.yaml -f compose.production.yaml \
     run --rm --no-deps backup run
   ```

4. Confirm `MEDIA_DATA_ROOT`, `BACKUP_ROOT`, `.env`, and reverse-proxy
   configuration are covered by the NAS backup/snapshot policy.
5. Record current and target application versions.

Database backup is required for patch, minor, and major upgrades.

## Upgrade

```bash
docker compose -f compose.yaml -f compose.production.yaml pull
docker compose -f compose.yaml -f compose.production.yaml build
docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini upgrade head
docker compose -f compose.yaml -f compose.production.yaml up -d --no-build
```

The normal API entrypoint also runs `upgrade head`; the explicit preflight makes a
migration failure visible before services are replaced. Omit `pull` for a source-only
deployment without published images.

## Verify

```bash
docker compose -f compose.yaml -f compose.production.yaml ps
docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini check
```

Then verify login, Operations, one image/video, an evaluation revision, a small
scan/upload, one portable export, worker heartbeat, backup freshness, and no stuck
jobs.

## Rollback

Alembic downgrade is not the guaranteed rollback. The reliable path:

1. Stop API, worker, and backup writes.
2. Preserve the failed database volume and logs.
3. Restore the pre-upgrade database backup.
4. deploy the matching previous application version.
5. Start services and repeat verification.

Never run an older application against a database migrated beyond its supported
schema.

## Secret rotation

Rotate `POSTGRES_PASSWORD` in PostgreSQL and `.env` in one maintenance window.
`CG_ADMIN_PASSWORD` is only bootstrap input after the administrator exists; a future
password-change command/UI must update the persisted account. Revoke and recreate
API tokens individually. Treat `.env`, dumps, exports, and NAS snapshots as private.
