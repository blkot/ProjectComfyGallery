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

### Targeted source deployments

When a change is isolated to one service and contains no migration or shared
runtime-contract change, rebuild and replace only that service. For a
frontend-only change:

```bash
docker compose -f compose.yaml -f compose.production.yaml build web
docker compose -f compose.yaml -f compose.production.yaml \
  up -d --no-deps --no-build web
```

This preserves API, worker, database, Redis, and backup containers. Docker can also
reuse the web dependency-install layer when `package.json` and `pnpm-lock.yaml` are
unchanged.

Do not use a targeted deployment when a database migration, shared API contract,
runtime dependency, environment contract, or cross-service version change is
involved. Use the full upgrade procedure in those cases.

On the J4125 NAS, avoid treating `docker compose build` as the default for every
source change: it evaluates and may rebuild all application services. Dependency
manifest/version changes invalidate expensive `uv sync` or `pnpm install` layers;
uncached base-image downloads and Alpine package upgrades add network-dependent
latency. The preferred long-term production path is CI-built, immutable
architecture-compatible images in a private registry, with the NAS limited to
`pull`, migration preflight, and `up`. A registry-backed BuildKit cache can also
retain dependency layers across release tags and NAS cache cleanup.

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
