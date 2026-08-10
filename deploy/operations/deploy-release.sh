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

echo "Validating the production Compose configuration."
docker compose "${compose_files[@]}" config --quiet

echo "Checking the currently scheduled backup service."
if docker inspect comfy-gallery-backup-1 >/dev/null 2>&1; then
  previous_backup_health="$(
    docker inspect comfy-gallery-backup-1 --format '{{.State.Health.Status}}' 2>/dev/null || true
  )"
  if [[ "$previous_backup_health" != "healthy" ]]; then
    echo "Warning: backup container health is ${previous_backup_health:-unknown}; requiring a fresh successful backup before continuing." >&2
  fi
fi

echo "Pulling the target backup image and creating a fresh database backup."
docker compose "${compose_files[@]}" pull backup
docker compose "${compose_files[@]}" run --rm --no-deps backup run
docker compose "${compose_files[@]}" run --rm --no-deps --entrypoint sh backup -c \
  "test -s /backups/.backup-status.json && grep -q '\"status\":\"ok\"' /backups/.backup-status.json"
echo "Fresh database backup verified."

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
  backup_state="$(
    docker inspect comfy-gallery-backup-1 --format '{{.State.Status}}' 2>/dev/null || true
  )"
  worker_state="$(
    docker inspect comfy-gallery-worker-1 --format '{{.State.Status}}' 2>/dev/null || true
  )"
  worker_background_state="$(
    docker inspect comfy-gallery-worker-background-1 --format '{{.State.Status}}' 2>/dev/null || true
  )"
  worker_spatial_state="$(
    docker inspect comfy-gallery-worker-spatial-1 --format '{{.State.Status}}' 2>/dev/null || true
  )"

  if [[ "$api_health" == "healthy" &&
    "$web_health" == "healthy" &&
    "$postgres_health" == "healthy" &&
    "$redis_health" == "healthy" &&
    "$backup_state" == "running" &&
    "$worker_state" == "running" &&
    "$worker_background_state" == "running" &&
    "$worker_spatial_state" == "running" ]]; then
    break
  fi
  sleep 2
done

if [[ "$api_health" != "healthy" ||
  "$web_health" != "healthy" ||
  "$postgres_health" != "healthy" ||
  "$redis_health" != "healthy" ||
  "$backup_state" != "running" ||
  "$worker_state" != "running" ||
  "$worker_background_state" != "running" ||
  "$worker_spatial_state" != "running" ]]; then
  docker compose "${compose_files[@]}" ps
  echo "Release health verification failed. Preserve logs and use the backup-based rollback runbook." >&2
  exit 1
fi

docker exec --user 10001:10001 comfy-gallery-backup-1 sh -c \
  "test -s /backups/.backup-status.json && grep -q '\"status\":\"ok\"' /backups/.backup-status.json"
if [[ "$backup_health" != "healthy" ]]; then
  echo "Backup service is running with a verified successful backup; Docker health is ${backup_health:-starting} and may lag until its five-minute probe." >&2
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
