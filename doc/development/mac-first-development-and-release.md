# Mac-First Development and Milestone Releases

**Status:** Implemented; first milestone-image publication pending

## Purpose

Ordinary development happens on the Mac. The production NAS remains pinned to its
last explicit milestone until a tested release is intentionally deployed. This
removes the J4125 build bottleneck and prevents incomplete work from touching
production data.

| Concern | Mac development | NAS production |
|---|---|---|
| CPU architecture | Native ARM64 | `linux/amd64` |
| API/worker/web | Native processes with reload | Immutable containers |
| PostgreSQL/Redis | Isolated development Compose project | Production Compose volumes |
| Media | `data/development` and private golden corpus | NAS managed/import roots |
| Deployment trigger | None | Explicit versioned milestone |
| Image construction | GitHub Actions | Pull only |

The Mac and NAS never share a database volume, Redis instance, managed-storage
directory, or administrator password.

## First local start

Requirements:

- Docker Desktop.
- `uv`.
- Node.js 24 and pnpm 11.
- ffmpeg/ffprobe.

Run:

```bash
make dev
```

The first run:

1. Copies `.env.development.example` to ignored `.env.development`.
2. Creates isolated paths beneath `data/development`.
3. Installs locked Python and frontend dependencies.
4. Starts PostgreSQL on `127.0.0.1:55432`.
5. Starts Redis on `127.0.0.1:56379`.
6. Applies Alembic migrations.
7. Creates the local administrator if missing.
8. Starts the API, one-thread reloadable worker, and Vite.

Open <http://127.0.0.1:5173>. Initial local-only credentials are:

```text
username: admin
password: comfygallery-local-development
```

Change `.env.development` when desired. It is ignored by Git and is not copied to
the NAS. If another local service already occupies the defaults, set
`DEV_API_PORT` or `DEV_WEB_PORT`; the launcher passes the selected API address to
Vite's development proxy automatically.

`Ctrl-C` stops API, worker, and Vite. PostgreSQL and Redis remain available so the
next start is fast.

Useful commands:

```bash
make dev-ready       # infrastructure, migration, and administrator only
make dev             # full foreground development stack
make dev-status      # PostgreSQL/Redis status
make dev-logs        # PostgreSQL/Redis logs
make dev-check       # complete Python/frontend checks
make dev-infra-down  # stop local PostgreSQL/Redis, retain their volumes
```

The development Compose project is named `comfy-gallery-development`; it cannot
address the production `comfy-gallery` named volumes by accident.

## Development media policy

Use:

- `data/development/import` for disposable local imports.
- `data/development/managed` for the local managed library.
- `testdata/golden` for the ignored private parser corpus.

Do not mount the NAS production managed-storage directory into the local API or
worker. When a real production case is needed, copy the minimum representative
file into the ignored golden corpus. Embedded prompts and model names remain
private.

Local ComfyUI synchronization is optional. Set `CG_COMFYUI_BASE_URL` in
`.env.development` only for a deliberate synchronization test.

## Normal change lifecycle

1. Implement on a requirement-scoped branch.
2. Run targeted tests during iteration.
3. Run `make dev-check` before publishing the branch.
4. Test the UI at `127.0.0.1:5173`.
5. Merge reviewed, passing work into `main`.
6. Leave the NAS on its existing milestone.

`main` is continuously tested source; it is not an instruction for the NAS to
deploy. Production tracks an explicit tag such as `v0.1.0-rc.8`.

## Creating a milestone

Before creating a tag:

1. Update every locked project/package version.
2. Change the Changelog's `Unreleased` section to a dated version heading.
3. Confirm `main` is clean and synchronized with `origin/main`.

Then run:

```bash
make milestone
```

`deploy/operations/create-milestone.sh` runs the complete test suite, validates
production Compose, creates an annotated `v<VERSION>` tag, and pushes only that
tag. It refuses dirty worktrees, non-main branches, mismatched versions, missing
Changelog entries, existing tags, or a local commit different from `origin/main`.

Pushing the tag starts `.github/workflows/release-images.yml`. GitHub Actions:

- verifies the tag exactly matches `VERSION`;
- builds backend, web, backup, PostgreSQL, and Redis images;
- targets only `linux/amd64`;
- publishes version and commit-SHA tags;
- uses per-image GitHub Actions build caches;
- generates BuildKit SBOM/provenance attestations in GHCR;
- additionally records GitHub repository attestations when the repository
  visibility/ownership supports them. GitHub does not offer that repository
  attestation service for user-owned private repositories.

Images use:

```text
ghcr.io/blkot/project-comfy-gallery/backend:<version>
ghcr.io/blkot/project-comfy-gallery/web:<version>
ghcr.io/blkot/project-comfy-gallery/backup:<version>
ghcr.io/blkot/project-comfy-gallery/postgres:<version>
ghcr.io/blkot/project-comfy-gallery/redis:<version>
```

The workflow authenticates with its repository-scoped `GITHUB_TOKEN` and
`packages: write`, following GitHub's
[container publishing guidance](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).

## One-time NAS registry authentication

The private NAS Docker client needs a GitHub personal access token (classic) with
only `read:packages`. GitHub documents this requirement for installing private
packages in
[GitHub Packages authentication](https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages#authenticating-to-github-packages).

Create that token in GitHub, then run on the Mac:

```bash
make nas-registry-login
```

The prompt does not echo the token. It streams the value directly to
`docker login --password-stdin` on the NAS and does not write it into the
repository, `.env`, shell history, or application database. Docker retains the
registry credential in the NAS user's Docker configuration.

## Deploying a completed milestone

After the Release images workflow is successful:

```bash
make nas-deploy RELEASE_VERSION=0.1.0-rc.8
```

The Mac wrapper verifies the matching GitHub Actions run completed successfully
and asks for exact version confirmation. The NAS then:

1. Verifies its repository worktree is clean.
2. Fetches and checks out the exact annotated release tag.
3. Creates a fresh database backup from the currently running container.
4. Pulls all versioned GHCR images.
5. Runs Alembic upgrade and schema-drift preflight using the new backend image.
6. Replaces services with `--no-build`.
7. Waits for API, web, PostgreSQL, Redis, backup, and worker health.
8. Confirms the API reports the requested application version.
9. Persists `CG_IMAGE_NAMESPACE` and `CG_IMAGE_TAG` in the ignored NAS `.env`.

The running release is not changed if image pull fails. Migration failure stops
before service replacement. If post-migration health fails, preserve logs and use
the backup-based rollback procedure; automatic Alembic downgrade is intentionally
not attempted.

## Architecture boundary

Local ARM64 execution validates application behavior quickly. The release workflow
is the authoritative container/platform validation for the x86 NAS. This separation
avoids slow ARM-to-AMD emulation on the Mac and avoids dependency compilation on
the J4125.

Source-building directly on the NAS remains an emergency diagnostic fallback, not
the normal production deployment path.
