#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repository_root"

release_version="${1:-}"
image_namespace="${CG_RELEASE_IMAGE_NAMESPACE:-ghcr.io/blkot/project-comfy-gallery}"
compose_files=(-f compose.yaml -f compose.production.yaml)

if [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  echo "Usage: $0 <release-version>" >&2
  exit 1
fi

if [[ "$(tr -d '[:space:]' < VERSION)" != "$release_version" ]]; then
  echo "Checked-out VERSION does not match ${release_version}." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Production .env is missing." >&2
  exit 1
fi

export CG_IMAGE_NAMESPACE="$image_namespace"
export CG_IMAGE_TAG="$release_version"

echo "Creating a database backup from the currently running release."
if docker inspect comfy-gallery-backup-1 >/dev/null 2>&1; then
  docker exec comfy-gallery-backup-1 comfy-gallery-backup
else
  docker compose "${compose_files[@]}" pull backup
  docker compose "${compose_files[@]}" run --rm --no-deps backup run
fi

echo "Pulling immutable ${release_version} images from ${image_namespace}."
docker compose "${compose_files[@]}" pull

echo "Running migration and schema-drift preflight."
docker compose "${compose_files[@]}" run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini upgrade head
docker compose "${compose_files[@]}" run --rm --no-deps api \
  alembic -c packages/py/core/alembic.ini check

echo "Replacing services without a NAS build."
docker compose "${compose_files[@]}" up -d --no-build

for _attempt in {1..60}; do
  api_health="$(docker inspect comfy-gallery-api-1 --format '{{.State.Health.Status}}' 2>/dev/null || true)"
  web_health="$(docker inspect comfy-gallery-web-1 --format '{{.State.Health.Status}}' 2>/dev/null || true)"
  postgres_health="$(
    docker inspect comfy-gallery-postgres-1 --format '{{.State.Health.Status}}' 2>/dev/null || true
  )"
  redis_health="$(
    docker inspect comfy-gallery-redis-1 --format '{{.State.Health.Status}}' 2>/dev/null || true
  )"
  backup_health="$(
    docker inspect comfy-gallery-backup-1 --format '{{.State.Health.Status}}' 2>/dev/null || true
  )"
  worker_state="$(
    docker inspect comfy-gallery-worker-1 --format '{{.State.Status}}' 2>/dev/null || true
  )"

  if [[ "$api_health" == "healthy" &&
    "$web_health" == "healthy" &&
    "$postgres_health" == "healthy" &&
    "$redis_health" == "healthy" &&
    "$backup_health" == "healthy" &&
    "$worker_state" == "running" ]]; then
    break
  fi
  sleep 2
done

if [[ "$api_health" != "healthy" ||
  "$web_health" != "healthy" ||
  "$postgres_health" != "healthy" ||
  "$redis_health" != "healthy" ||
  "$backup_health" != "healthy" ||
  "$worker_state" != "running" ]]; then
  docker compose "${compose_files[@]}" ps
  echo "Release health verification failed. Preserve logs and use the backup-based rollback runbook." >&2
  exit 1
fi

reported_version="$(
  docker exec comfy-gallery-api-1 python -c \
    "import json, urllib.request; print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/live'))['version'])"
)"
if [[ "$reported_version" != "$release_version" ]]; then
  echo "API reported ${reported_version}; expected ${release_version}." >&2
  exit 1
fi

set_environment_value() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '\n%s=%s\n' "$key" "$value" >> .env
  fi
}

set_environment_value CG_IMAGE_NAMESPACE "$image_namespace"
set_environment_value CG_IMAGE_TAG "$release_version"

docker compose "${compose_files[@]}" ps
echo "Project Comfy Gallery ${release_version} is healthy."
