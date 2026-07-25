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

## Standard milestone upgrade

Normal releases are built once by GitHub Actions as immutable `linux/amd64`
images. The NAS pulls those images; it does not rebuild application source.

### One-time private registry login

From the development Mac:

```bash
make nas-registry-login
```

Enter a GitHub classic personal access token with `read:packages`. The token is
sent directly to `docker login` on the NAS and is not written to this
repository or its environment files.

### Create and deploy a milestone

After the release version and changelog are finalized on `main`:

```bash
make milestone RELEASE_VERSION=0.1.0
```

This verifies the release, creates and pushes the matching annotated Git tag,
and starts the GitHub Actions image build. After the `Release container images`
workflow succeeds:

```bash
make nas-deploy RELEASE_VERSION=0.1.0
```

The deployment wrapper confirms the successful workflow run, asks for explicit
confirmation, checks out the exact tag on the NAS, creates a database backup,
pulls the tagged images, runs migrations, starts services with `--no-build`,
and waits for health and version checks.

The current NAS release remains active if image pulling or the migration
preflight fails. A failed post-start health check is reported and must be
investigated before another deployment.

## Manual NAS recovery path

Use this only when the Mac wrapper is unavailable. On the NAS, from the
repository checkout for the exact release tag:

```bash
export CG_IMAGE_NAMESPACE=ghcr.io/blkot/project-comfy-gallery
export CG_IMAGE_TAG=0.1.0
./deploy/operations/deploy-release.sh 0.1.0
```

The NAS must already be authenticated to GHCR.

## Emergency source-build fallback

Building application images from source on the J4125 NAS is retained only as
an emergency fallback. Run from the repository root:

```bash
docker compose -f compose.yaml -f compose.production.yaml pull
docker compose -f compose.yaml -f compose.production.yaml build
docker compose -f compose.yaml -f compose.production.yaml \
  run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini upgrade head
docker compose -f compose.yaml -f compose.production.yaml \
  up -d --no-build
```

The normal API entrypoint also runs `upgrade head`; the explicit preflight makes
a migration failure visible before services are replaced.

When an emergency change is isolated to one service and contains no migration
or shared runtime-contract change, only that service may be rebuilt and
replaced. For a frontend-only change:

```bash
docker compose -f compose.yaml -f compose.production.yaml build web
docker compose -f compose.yaml -f compose.production.yaml \
  up -d --no-deps --no-build web
```

Do not use a targeted deployment when a database migration, shared API
contract, runtime dependency, environment contract, or cross-service version
change is involved.

Measured on the target J4125 NAS on 2026-07-25, a CSS-only web build took 84
seconds: roughly 61 seconds resolving the already pinned Node/Nginx image metadata,
18.7 seconds running the frontend build, and about four seconds exporting the
image. `pnpm install` and the Alpine hardening layer were cache hits. Replacing the
web container took three seconds. This measurement distinguishes registry latency
from application compilation and supports targeted deployment as the immediate
workflow.

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
