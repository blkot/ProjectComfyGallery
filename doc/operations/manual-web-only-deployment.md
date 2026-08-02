# Manual Web-Only Deployment

**Status:** Implemented operational procedure

## Purpose

This runbook deploys a frontend-only change to the Xanta NAS without restarting
the API, worker, PostgreSQL, Redis, or backup services. It is intended for
emergency or pre-release deployment of local web changes that have not yet been
published as an immutable milestone image.

The replacement command is deliberately scoped to the `web` service and uses
both `--no-deps` and `--no-build`:

```bash
docker compose -f compose.yaml -f compose.production.yaml \
  up -d --no-deps --no-build --force-recreate web
```

An in-progress ComfyUI API upload or worker job continues running when the API
and worker container identities remain unchanged.

## Applicability

Use this procedure only when every material change is contained in the web build
inputs:

- `apps/web/`
- `package.json`
- `pnpm-lock.yaml`
- `pnpm-workspace.yaml`
- `deploy/docker/web.Dockerfile`
- `deploy/docker/nginx.conf`

Do not use a targeted web deployment when the change includes:

- an API or worker change;
- a database migration;
- a shared API or runtime contract change;
- an environment-variable contract change;
- a Compose topology or cross-service version change.

Use the full [upgrade runbook](upgrade-runbook.md) for those changes.

## Known target

- NAS helper: `~/.local/bin/xanta-nas`
- SSH alias: `xanta-nas`
- Production checkout:
  `/share/homes/xanta/data/docker_data/ProjectComfyGallery`
- Compose project: `comfy-gallery`
- Web container: `comfy-gallery-web-1`
- API container: `comfy-gallery-api-1`
- Worker container: `comfy-gallery-worker-1`
- LAN health URL: `http://192.168.50.68:8181/healthz`

The current QNAP Docker installation does not provide `docker buildx`. The
repository web Dockerfile uses BuildKit cache mounts, so this procedure creates
an isolated build context and a temporary legacy-compatible Dockerfile. The only
change in that temporary Dockerfile is removal of the two cache-mount hints;
the dependency installation, frontend build, pinned base images, Nginx
configuration, labels, and runtime image remain the same.

## 1. Verify the frontend on the Mac

From the repository root:

```bash
cd /Users/wangshenhao/Documents/ProjectComfyGallery

pnpm --filter @comfy-gallery/web test
pnpm --filter @comfy-gallery/web check
pnpm --filter @comfy-gallery/web build
```

Review the candidate build inputs:

```bash
git status --short -- \
  apps/web \
  package.json \
  pnpm-lock.yaml \
  pnpm-workspace.yaml \
  deploy/docker/web.Dockerfile \
  deploy/docker/nginx.conf

git diff --name-only -- \
  apps/web \
  package.json \
  pnpm-lock.yaml \
  pnpm-workspace.yaml \
  deploy/docker/web.Dockerfile \
  deploy/docker/nginx.conf
```

Stop if the deployment is not frontend-only.

## 2. Create an isolated NAS build context

Run these commands in one Mac terminal:

```bash
REMOTE_CTX="/share/homes/xanta/data/docker_data/.manual-web-$(date +%Y%m%d-%H%M%S)"
LEGACY_DOCKERFILE="/tmp/comfy-gallery-web.Dockerfile"

sed \
  -e '/^RUN --mount=type=cache,target=\/pnpm\/store/d' \
  -e '/^    --mount=type=cache,target=\/root\/.cache\/node\/corepack/d' \
  -e 's/^    pnpm config set store-dir/RUN pnpm config set store-dir/' \
  deploy/docker/web.Dockerfile > "$LEGACY_DOCKERFILE"

ssh xanta-nas "mkdir -p '$REMOTE_CTX'"

rsync -azR \
  --exclude='node_modules/' \
  --exclude='dist/' \
  package.json \
  pnpm-lock.yaml \
  pnpm-workspace.yaml \
  apps/web \
  deploy/docker/nginx.conf \
  .dockerignore \
  xanta-nas:"$REMOTE_CTX/"

rsync -az "$LEGACY_DOCKERFILE" \
  xanta-nas:"$REMOTE_CTX/web.Dockerfile"

printf 'Remote build context: %s\n' "$REMOTE_CTX"
```

Copy the printed path. The production checkout remains clean because all build
inputs are staged in the isolated directory.

## 3. Capture the live state and create a rollback image

Open a NAS shell:

```bash
~/.local/bin/xanta-nas
```

Set the paths. Replace the example timestamp with the path printed in the
previous step:

```bash
PROD_DIR="/share/homes/xanta/data/docker_data/ProjectComfyGallery"
REMOTE_CTX="/share/homes/xanta/data/docker_data/.manual-web-YYYYMMDD-HHMMSS"

cd "$PROD_DIR"

WEB_REF="$(docker inspect comfy-gallery-web-1 --format '{{.Config.Image}}')"
OLD_WEB_IMAGE="$(docker inspect comfy-gallery-web-1 --format '{{.Image}}')"
API_BEFORE="$(docker inspect comfy-gallery-api-1 --format '{{.Id}}')"
WORKER_BEFORE="$(docker inspect comfy-gallery-worker-1 --format '{{.Id}}')"
ROLLBACK_REF="${WEB_REF}-before-manual-$(date +%Y%m%d-%H%M%S)"
ALPINE_MIRROR="$(sed -n 's/^ALPINE_MIRROR=//p' .env | tail -n 1)"

docker tag "$OLD_WEB_IMAGE" "$ROLLBACK_REF"

printf 'Target image:   %s\n' "$WEB_REF"
printf 'Rollback image: %s\n' "$ROLLBACK_REF"
printf 'Alpine mirror:  %s\n' "$ALPINE_MIRROR"
printf 'API before:     %s\n' "$API_BEFORE"
printf 'Worker before:  %s\n' "$WORKER_BEFORE"
```

Keep the shell open so these values remain available for verification and
rollback.

## 4. Build only the web image

From the same NAS shell:

```bash
cd "$REMOTE_CTX"

DOCKER_BUILDKIT=0 docker build \
  --file web.Dockerfile \
  --tag "$WEB_REF" \
  --build-arg CG_PROJECT_VERSION="${WEB_REF##*:}" \
  --build-arg CG_REVISION="manual-$(date +%Y%m%d-%H%M%S)" \
  --build-arg ALPINE_MIRROR="${ALPINE_MIRROR:-https://dl-cdn.alpinelinux.org/alpine}" \
  .
```

Do not continue if the build fails. No live container has been changed at this
point.

Inspect the completed image:

```bash
docker image inspect "$WEB_REF" \
  --format 'image={{.Id}} version={{index .Config.Labels "org.opencontainers.image.version"}} revision={{index .Config.Labels "org.opencontainers.image.revision"}}'
```

## 5. Replace only the web container

From the same NAS shell:

```bash
cd "$PROD_DIR"

docker compose \
  -f compose.yaml \
  -f compose.production.yaml \
  up -d \
  --no-deps \
  --no-build \
  --force-recreate \
  web
```

Do not use any of the following for this procedure:

```text
docker compose down
docker compose up -d
make prod-up
deploy/operations/deploy-release.sh
```

Those commands have a broader service scope.

## 6. Verify health and service isolation

Wait for the web health check to reach a terminal state:

```bash
attempt=0
while [ "$attempt" -lt 30 ]; do
  WEB_HEALTH="$(docker inspect comfy-gallery-web-1 \
    --format '{{.State.Health.Status}}')"
  [ "$WEB_HEALTH" = "healthy" ] && break
  [ "$WEB_HEALTH" = "unhealthy" ] && break
  attempt=$((attempt + 1))
  sleep 2
done

printf 'Web health: %s\n' "$WEB_HEALTH"
test "$WEB_HEALTH" = "healthy"
```

Verify the frontend and backend health endpoints:

```bash
docker exec comfy-gallery-web-1 \
  wget -qO- http://127.0.0.1:8080/healthz

docker exec comfy-gallery-api-1 python -c \
  'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=5).read().decode())'
```

Confirm that the API and worker were not recreated:

```bash
API_AFTER="$(docker inspect comfy-gallery-api-1 --format '{{.Id}}')"
WORKER_AFTER="$(docker inspect comfy-gallery-worker-1 --format '{{.Id}}')"

test "$API_AFTER" = "$API_BEFORE" && echo "API unchanged"
test "$WORKER_AFTER" = "$WORKER_BEFORE" && echo "Worker unchanged"

docker compose -f compose.yaml -f compose.production.yaml \
  ps web api worker postgres redis
```

Both identity comparisons must succeed. PostgreSQL and Redis must remain
healthy.

From the Mac, verify LAN access:

```bash
curl --fail --show-error http://192.168.50.68:8181/healthz
```

The expected response is:

```text
ok
```

Complete a short browser smoke test:

1. Sign in.
2. Open the Media Library.
3. Exercise the changed frontend behavior.
4. Confirm an existing media detail page still loads.
5. Confirm Operations reports a healthy API and worker.

## Rollback

If the new web image or smoke test fails, use the values retained in the same NAS
shell:

```bash
docker tag "$ROLLBACK_REF" "$WEB_REF"

cd "$PROD_DIR"

docker compose \
  -f compose.yaml \
  -f compose.production.yaml \
  up -d \
  --no-deps \
  --no-build \
  --force-recreate \
  web
```

Repeat all health and container-identity checks. This rollback replaces only the
web container.

If the original shell was lost, locate the retained rollback image before
proceeding:

```bash
docker image ls \
  --format '{{.Repository}}:{{.Tag}} {{.ID}}' |
  grep 'before-manual'
```

Use the exact matching rollback reference as the source of the `docker tag`
command.

## Cleanup

After successful verification, remove only the isolated build context:

```bash
case "$REMOTE_CTX" in
  /share/homes/xanta/data/docker_data/.manual-web-*)
    find "$REMOTE_CTX" -depth -delete
    ;;
  *)
    echo "Refusing unexpected cleanup path: $REMOTE_CTX" >&2
    ;;
esac
```

Back on the Mac:

```bash
unlink /tmp/comfy-gallery-web.Dockerfile
```

Retain the rollback image until the new frontend has completed its intended
stability window.

## Buildx-enabled fast path

If the NAS later gains a working Buildx installation and its repository checkout
already contains the exact frontend source to deploy, the isolated-context
workaround can be replaced with:

```bash
cd /share/homes/xanta/data/docker_data/ProjectComfyGallery

docker compose -f compose.yaml -f compose.production.yaml build web
docker compose -f compose.yaml -f compose.production.yaml \
  up -d --no-deps --no-build --force-recreate web
```

The rollback capture and verification steps remain required.
