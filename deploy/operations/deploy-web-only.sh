#!/usr/bin/env bash

set -Eeuo pipefail
umask 022

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
nas_helper="${XANTA_NAS_HELPER:-${HOME}/.local/bin/xanta-nas}"
nas_ssh_host="${XANTA_NAS_SSH_HOST:-xanta-nas}"
remote_repository="${XANTA_COMFY_GALLERY_REPOSITORY:-/share/homes/xanta/data/docker_data/ProjectComfyGallery}"
lan_health_url="${XANTA_COMFY_GALLERY_WEB_HEALTH_URL:-http://192.168.50.68:8181/healthz}"
lan_root_url="${XANTA_COMFY_GALLERY_WEB_ROOT_URL:-${lan_health_url%/healthz}/}"

confirmation=false
dry_run=false
keep_context=false

usage() {
  cat <<'EOF'
Usage: deploy/operations/deploy-web-only.sh [options]

Build and deploy the current local frontend to the Xanta NAS without recreating
the API, workers, PostgreSQL, Redis, or backup containers.

Options:
  --yes           Deploy without the interactive confirmation.
  --dry-run       Run local verification and build, but do not change the NAS.
  --keep-context  Keep the isolated NAS build context for troubleshooting.
  -h, --help      Show this help.

Environment overrides:
  XANTA_NAS_HELPER
  XANTA_NAS_SSH_HOST
  XANTA_COMFY_GALLERY_REPOSITORY
  XANTA_COMFY_GALLERY_WEB_HEALTH_URL
  XANTA_COMFY_GALLERY_WEB_ROOT_URL
EOF
}

while (($# > 0)); do
  case "$1" in
    --yes)
      confirmation=true
      ;;
    --dry-run)
      dry_run=true
      ;;
    --keep-context)
      keep_context=true
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

cd "$repository_root"

for required_command in git pnpm rsync curl ssh; do
  if ! command -v "$required_command" >/dev/null 2>&1; then
    echo "Required command is unavailable: $required_command" >&2
    exit 1
  fi
done

if [[ ! -x "$nas_helper" && "$dry_run" != true ]]; then
  echo "NAS helper is not executable: $nas_helper" >&2
  exit 1
fi

if [[ ! -f deploy/docker/web-overlay.Dockerfile ]]; then
  echo "Missing deploy/docker/web-overlay.Dockerfile" >&2
  exit 1
fi
if [[ ! -f deploy/docker/nginx.conf ]]; then
  echo "Missing deploy/docker/nginx.conf" >&2
  exit 1
fi

echo "Running frontend tests, checks, and production build."
pnpm --filter @comfy-gallery/web test
pnpm --filter @comfy-gallery/web check
pnpm --filter @comfy-gallery/web build
test -s apps/web/dist/index.html

unreadable_file="$(find apps/web/dist -type f ! -perm -004 -print -quit)"
untraversable_directory="$(find apps/web/dist -type d ! -perm -005 -print -quit)"
if [[ -n "$unreadable_file" || -n "$untraversable_directory" ]]; then
  echo "Frontend build output is not readable by the nginx worker." >&2
  [[ -n "$unreadable_file" ]] && echo "Unreadable file: $unreadable_file" >&2
  [[ -n "$untraversable_directory" ]] && \
    echo "Untraversable directory: $untraversable_directory" >&2
  exit 1
fi

echo
echo "Frontend candidate worktree state:"
git status --short -- \
  apps/web \
  package.json \
  pnpm-lock.yaml \
  pnpm-workspace.yaml \
  deploy/docker/nginx.conf \
  deploy/docker/web-overlay.Dockerfile

if [[ "$dry_run" == true ]]; then
  echo
  echo "Dry run complete. No NAS state was changed."
  exit 0
fi

if [[ "$confirmation" != true ]]; then
  echo
  read -r -p "Deploy this frontend bundle to the Xanta NAS? [y/N]: " answer
  if [[ "${answer,,}" != "y" ]]; then
    echo "Deployment cancelled."
    exit 1
  fi
fi

deploy_id="manual-web-$(date +%Y%m%d-%H%M%S)-$$"
remote_context="/share/homes/xanta/data/docker_data/.${deploy_id}"
revision="${deploy_id}-$(git rev-parse --short=12 HEAD)"
if [[ -n "$(git status --porcelain -- apps/web package.json pnpm-lock.yaml pnpm-workspace.yaml deploy/docker/nginx.conf)" ]]; then
  revision="${revision}-dirty"
fi

remote_context_created=false

cleanup_remote_context() {
  if [[ "$remote_context_created" != true || "$keep_context" == true ]]; then
    return
  fi

  set +e
  "$nas_helper" sh -c '
    target="$1"
    case "$target" in
      /share/homes/xanta/data/docker_data/.manual-web-*)
        if [ -d "$target" ]; then
          find "$target" -depth -delete
        fi
        ;;
      *)
        echo "Refusing unexpected cleanup path: $target" >&2
        exit 1
        ;;
    esac
  ' -- "$remote_context" >/dev/null
  set -e
}

trap cleanup_remote_context EXIT

echo
echo "Creating isolated build context: $remote_context"
"$nas_helper" mkdir -p "$remote_context/dist"
remote_context_created=true
rsync -az --delete apps/web/dist/ "$nas_ssh_host:$remote_context/dist/"
rsync -az deploy/docker/web-overlay.Dockerfile \
  "$nas_ssh_host:$remote_context/web-overlay.Dockerfile"
rsync -az deploy/docker/nginx.conf "$nas_ssh_host:$remote_context/nginx.conf"

"$nas_helper" bash -s -- \
  "$remote_repository" \
  "$remote_context" \
  "$revision" \
  "$deploy_id" \
  "$keep_context" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

remote_repository="$1"
remote_context="$2"
revision="$3"
deploy_id="$4"
keep_context="$5"
compose_files=(-f compose.yaml -f compose.production.yaml)

cd "$remote_repository"
test -f compose.yaml
test -f compose.production.yaml
test -f .env

service_id() {
  docker compose "${compose_files[@]}" ps -q "$1"
}

container_health() {
  docker inspect "$1" --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
}

wait_for_web() {
  local container_id="$1"
  local attempt=0
  local health=""

  while ((attempt < 30)); do
    health="$(container_health "$container_id" 2>/dev/null || true)"
    case "$health" in
      healthy)
        return 0
        ;;
      unhealthy | exited | dead)
        return 1
        ;;
    esac
    attempt=$((attempt + 1))
    sleep 2
  done
  return 1
}

cleanup_context() {
  if [[ "$keep_context" == true ]]; then
    echo "Retaining NAS build context: $remote_context"
    return
  fi

  case "$remote_context" in
    /share/homes/xanta/data/docker_data/.manual-web-*)
      if [[ -d "$remote_context" ]]; then
        find "$remote_context" -depth -delete
      fi
      ;;
    *)
      echo "Refusing unexpected cleanup path: $remote_context" >&2
      return 1
      ;;
  esac
}

web_before="$(service_id web)"
api_before="$(service_id api)"
worker_before="$(service_id worker)"
worker_background_before="$(service_id worker-background)"
postgres_before="$(service_id postgres)"
redis_before="$(service_id redis)"
backup_before="$(service_id backup)"

for container_id in \
  "$web_before" \
  "$api_before" \
  "$worker_before" \
  "$worker_background_before" \
  "$postgres_before" \
  "$redis_before" \
  "$backup_before"; do
  if [[ -z "$container_id" ]]; then
    echo "A required production service is not running; refusing deployment." >&2
    exit 1
  fi
done

web_health_before="$(container_health "$web_before")"
api_health_before="$(container_health "$api_before")"
worker_health_before="$(container_health "$worker_before")"
worker_background_health_before="$(container_health "$worker_background_before")"
postgres_health_before="$(container_health "$postgres_before")"
redis_health_before="$(container_health "$redis_before")"
backup_health_before="$(container_health "$backup_before")"

printf '%s\n' \
  "Pre-deploy health: web=$web_health_before api=$api_health_before" \
  "  worker=$worker_health_before worker-background=$worker_background_health_before" \
  "  postgres=$postgres_health_before redis=$redis_health_before backup=$backup_health_before"

if [[ "$backup_health_before" != healthy ]]; then
  echo "Warning: backup health is $backup_health_before; continuing because this deployment does not change the backup service." >&2
fi

if [[ "$web_health_before" != healthy ||
  "$api_health_before" != healthy ||
  "$postgres_health_before" != healthy ||
  "$redis_health_before" != healthy ||
  "$worker_health_before" != running ||
  "$worker_background_health_before" != running ]]; then
  docker compose "${compose_files[@]}" ps
  echo "A service required for safe frontend deployment is not healthy; refusing to continue." >&2
  exit 1
fi

web_ref="$(docker inspect "$web_before" --format '{{.Config.Image}}')"
old_web_image="$(docker inspect "$web_before" --format '{{.Image}}')"
if [[ "$web_ref" == sha256:* || "$web_ref" == *@sha256:* || "$web_ref" != *:* ]]; then
  echo "The running web container does not have a reusable tagged image reference: $web_ref" >&2
  exit 1
fi
rollback_ref="${web_ref}-before-${deploy_id}"
image_tag_may_change=false
web_replace_attempted=false

rollback_on_error() {
  local failed_status="$1"
  trap - ERR HUP INT TERM
  set +e

  echo "Frontend deployment failed; restoring the previous web image." >&2
  if [[ "$image_tag_may_change" == true ]]; then
    docker tag "$rollback_ref" "$web_ref"
  fi
  if [[ "$web_replace_attempted" == true ]]; then
    cd "$remote_repository"
    docker compose "${compose_files[@]}" \
      up -d --no-deps --no-build --force-recreate web
    restored_web="$(service_id web)"
    if ! wait_for_web "$restored_web"; then
      echo "Automatic rollback ran, but the restored web container is not healthy." >&2
      docker logs --tail 120 "$restored_web" >&2
    else
      echo "Previous frontend restored successfully." >&2
    fi
  fi
  cd "$remote_repository"
  cleanup_context
  exit "$failed_status"
}

trap 'rollback_on_error $?' ERR
trap 'rollback_on_error 129' HUP
trap 'rollback_on_error 130' INT
trap 'rollback_on_error 143' TERM

docker tag "$old_web_image" "$rollback_ref"
echo "Rollback image: $rollback_ref"

cd "$remote_context"
image_tag_may_change=true
build_web_image() {
  DOCKER_BUILDKIT=0 docker build \
    --file web-overlay.Dockerfile \
    --tag "$web_ref" \
    --build-arg "BASE_IMAGE=$rollback_ref" \
    --build-arg "CG_PROJECT_VERSION=${web_ref##*:}" \
    --build-arg "CG_REVISION=$revision" \
    .
}

build_completed=false
build_attempt=1
while ((build_attempt <= 2)); do
  echo "Building NAS web image (attempt ${build_attempt}/2)."
  if build_web_image; then
    build_completed=true
    break
  fi
  if ((build_attempt < 2)); then
    echo "The QNAP legacy builder failed; retrying once with its completed cache."
    sleep 2
  fi
  build_attempt=$((build_attempt + 1))
done
test "$build_completed" = true
new_web_image="$(docker image inspect "$web_ref" --format '{{.Id}}')"

cd "$remote_repository"
web_replace_attempted=true
docker compose "${compose_files[@]}" \
  up -d --no-deps --no-build --force-recreate web

web_after="$(service_id web)"
test -n "$web_after"
if ! wait_for_web "$web_after"; then
  docker logs --tail 120 "$web_after" >&2
  false
fi

test "$web_after" != "$web_before"
test "$(docker inspect "$web_after" --format '{{.Image}}')" = "$new_web_image"
test "$(service_id api)" = "$api_before"
test "$(service_id worker)" = "$worker_before"
test "$(service_id worker-background)" = "$worker_background_before"
test "$(service_id postgres)" = "$postgres_before"
test "$(service_id redis)" = "$redis_before"
test "$(service_id backup)" = "$backup_before"

test "$(docker exec "$web_after" wget -qO- http://127.0.0.1:8080/healthz)" = ok
docker exec "$web_after" wget -qO- http://127.0.0.1:8080/ >/dev/null
web_port="$(sed -n 's/^WEB_PORT=//p' .env | tail -1)"
web_port="${web_port:-8080}"
test "$(curl -fsS --max-time 10 "http://127.0.0.1:${web_port}/healthz")" = ok
curl -fsS --max-time 10 "http://127.0.0.1:${web_port}/" >/dev/null

docker compose "${compose_files[@]}" ps
echo "Frontend deployment is healthy."
echo "Web image: $new_web_image"
echo "Revision: $revision"
echo "Rollback image: $rollback_ref"
echo "API, workers, PostgreSQL, Redis, and backup container IDs are unchanged."

trap - ERR HUP INT TERM
cleanup_context
REMOTE_SCRIPT

remote_context_created=false

echo
echo "Verifying LAN endpoint: $lan_health_url"
test "$(curl -fsS --max-time 10 "$lan_health_url")" = ok
echo "Verifying LAN main page: $lan_root_url"
curl -fsS --max-time 10 "$lan_root_url" >/dev/null
echo "Frontend-only NAS deployment completed successfully."
