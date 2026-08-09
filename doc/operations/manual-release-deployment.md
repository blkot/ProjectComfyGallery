# Manual Milestone Deployment to the Xanta NAS

**Status:** Implemented operator runbook

This is the explicit, step-by-step path for a release that changes the backend,
API, worker, database schema, Python dependencies, Compose contract, or more than
one runtime service. Run the release preparation commands on the development Mac.
The NAS pulls immutable AMD64 images built by GitHub Actions; it does not need
`make` and does not build the application.

For the current workflow-input work, use a full milestone release because it adds
the `0012_workflow_input_media` migration and changes the API, worker, shared core,
web client, Compose configuration, and backup behavior. A web-only deployment is
not safe.

The examples below use `0.1.0-rc.18`. Replace it consistently if a different
version is chosen.

## 1. Inspect the proposed deployment

From the repository root on the Mac:

```bash
./deploy/operations/deploy-xanta-auto.sh plan
```

For this release, the result must be `release`. Review every file shown under
`Full release`. The command is read-only and also reports the release currently
running on the NAS.

## 2. Finalize release metadata

The release number is deliberately locked in package metadata, runtime version
constants, Compose/Docker defaults, and release tests. Changing only `VERSION`
will make `test_release_version.py` fail. Update the complete lock set from the old
version to the new version:

- `VERSION`;
- the root, API, worker, and core `pyproject.toml` files;
- API, worker, and core `__version__` constants;
- root and web `package.json`;
- `compose.yaml` and all six release Dockerfiles;
- release-version and health test expectations;
- the README locked-release declaration.

Set those release locks to exactly:

```text
0.1.0-rc.18
```

Move the completed entries under `## Unreleased` in `CHANGELOG.md` into a dated
heading while preserving a new empty Unreleased heading:

```markdown
## Unreleased

## 0.1.0-rc.18 — 2026-08-09

- Describe the workflow-input capture and deployment improvements.
```

The version has three forms with different purposes:

- `0.1.0-rc.18` in `VERSION`, the Changelog heading, image tags, and script arguments;
- `v0.1.0-rc.18` as the Git tag;
- `CG_IMAGE_TAG=0.1.0-rc.18` in the NAS `.env` after a successful deployment.

Do not create the Git tag manually. The milestone script creates and pushes it
after all checks pass.

After editing the locks, refresh generated version-bearing artifacts:

```bash
uv lock --offline
uv run python scripts/export_openapi.py
```

Use this audit to distinguish unintended stale locks from historical Changelog or
currently deployed-production references:

```bash
rg '0\.1\.0-rc\.17|0\.1\.0-rc\.18'
```

## 3. Verify the complete source tree

Run:

```bash
make check
POSTGRES_PASSWORD=release-validation \
  CG_ADMIN_PASSWORD=release-validation \
  CG_IMAGE_TAG=0.1.0-rc.18 \
  docker compose -f compose.yaml -f compose.production.yaml config --quiet
git diff --check
```

If `make` is unavailable on the Mac, its complete equivalent is:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
pnpm check
pnpm test
```

Stop on any failure. Do not tag a release with a failing check.

## 4. Commit and push `main`

Review and intentionally stage the release files:

```bash
git status --short
git diff --stat
git add <reviewed-files>
git commit -m "feat: capture and display workflow input media"
git push origin main
```

Then confirm the worktree is clean and local `main` exactly matches GitHub:

```bash
git status --short --branch
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

The second command prints nothing when it succeeds. If it fails, fetch and inspect
the divergence instead of force-pushing.

## 5. Run a non-publishing milestone preflight

```bash
./deploy/operations/create-milestone.sh 0.1.0-rc.18 --dry-run
```

This repeats the release checks and validates the production Compose contract. It
does not create a tag, start GitHub Actions, or modify the NAS.

## 6. Publish the milestone tag

```bash
./deploy/operations/create-milestone.sh 0.1.0-rc.18
```

This script:

1. verifies `VERSION` and the dated Changelog heading;
2. requires a clean `main` synchronized with `origin/main`;
3. runs the full verification suite;
4. creates annotated tag `v0.1.0-rc.18`;
5. pushes the tag to GitHub.

Pushing the tag starts the `Release images` GitHub Actions workflow. If this step
finishes successfully, do not create or push the same tag again.

## 7. Wait for immutable AMD64 images

The deploy wrapper now waits for the workflow automatically, so this inspection is
optional:

```bash
gh run list \
  --repo blkot/ProjectComfyGallery \
  --workflow release-images.yml \
  --branch v0.1.0-rc.18 \
  --limit 5
```

To watch a specific run, copy its numeric ID from `gh run list` and run:

```bash
gh run watch <run-id> \
  --repo blkot/ProjectComfyGallery \
  --exit-status
```

Do not deploy if any image job failed. Fix the source, choose a new version, and
publish a new tag; release tags are immutable.

## 8. Deploy from the Mac

```bash
./deploy/operations/deploy-xanta-release.sh 0.1.0-rc.18
```

The script waits up to 45 minutes for the matching image workflow. When prompted,
type exactly:

```text
0.1.0-rc.18
```

It then performs these operations on the NAS:

1. refuses a dirty production checkout;
2. fetches and checks out exact tag `v0.1.0-rc.18` in detached mode;
3. validates the production Compose configuration;
4. pulls the target backup image and creates a verified database backup;
5. pulls the complete immutable image set;
6. applies Alembic migrations and checks for schema drift;
7. replaces containers with `--no-build`;
8. waits for API, web, PostgreSQL, Redis, both workers, and backup service state;
9. verifies the API reports `0.1.0-rc.18`;
10. writes the successful image namespace and tag to the NAS `.env`.

The pre-deployment backup is created by a one-off target-version backup container,
not by executing as root inside the scheduled backup container. This prevents the
root-owned retention problem found on the `rc.17` NAS deployment.

Use `--no-wait` only when a script or operator has already confirmed the images:

```bash
./deploy/operations/deploy-xanta-release.sh \
  0.1.0-rc.18 \
  --no-wait
```

Use `--yes` only in controlled automation because it removes the final typed
confirmation.

## 9. Verify production

From the Mac:

```bash
./deploy/operations/deploy-xanta-auto.sh status
curl --fail --show-error http://192.168.50.68:8181/health/live
```

Confirm migration state on the NAS:

```bash
xanta-nas sh -lc '
  cd /share/homes/xanta/data/docker_data/ProjectComfyGallery
  docker compose -f compose.yaml -f compose.production.yaml \
    run --rm --no-deps api \
    alembic -c packages/py/core/alembic.ini current
'
```

For this release, Alembic should report `0012_workflow_input_media (head)`. Then
open the application and verify login, Media Detail, captured workflow inputs, one
small import, worker progress, and Operations backup status.

## Direct NAS fallback

Use this only when the Mac deployment wrapper is unavailable and the release tag
and images already exist. The NAS does not need `make`:

```bash
xanta-nas
cd /share/homes/xanta/data/docker_data/ProjectComfyGallery
test -z "$(/opt/bin/git status --porcelain)"
/opt/bin/git fetch --tags origin
/opt/bin/git checkout --detach v0.1.0-rc.18
./deploy/operations/deploy-release.sh 0.1.0-rc.18
```

Do not manually run `docker compose down`. The release script preserves the
running services until backup, image pull, and migration preflight have succeeded.

## One-command automation after commit and push

After Steps 1–4 are complete, the dispatcher can perform Steps 5–9:

```bash
./deploy/operations/deploy-xanta-auto.sh \
  ship \
  --release-version 0.1.0-rc.18
```

`ship` creates the tag only when it is missing, waits for GitHub-built images,
asks for deployment confirmation, deploys, and verifies the NAS. It refuses dirty
or unpushed source.

Run its strict no-write preflight first when desired:

```bash
./deploy/operations/deploy-xanta-auto.sh \
  ship \
  --release-version 0.1.0-rc.18 \
  --dry-run
```

The dry run performs milestone verification but neither publishes a tag nor
changes the NAS.

## Common refusal messages

- **`VERSION does not match`** — update `VERSION` or pass the version already in it.
- **`CHANGELOG.md must contain a dated heading`** — add `## <version> — <date>`.
- **`worktree must be clean`** — review, commit, or intentionally discard remaining changes.
- **`Local main must exactly match origin/main`** — push the release commit or inspect divergence.
- **`tag already exists`** — do not move it; use a new release version.
- **release images failed** — inspect GitHub Actions and publish a new version after fixing the cause.
- **fresh database backup failed** — stop before migration and diagnose backup storage/database access.
- **migration failed** — services remain on the prior release; do not force container replacement.
