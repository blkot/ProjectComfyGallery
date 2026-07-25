#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
environment_runner="$repository_root/deploy/development/with-env.sh"
child_pids=()

stop_children() {
  local child_pid
  trap - EXIT INT TERM
  for child_pid in "${child_pids[@]:-}"; do
    if kill -0 "$child_pid" >/dev/null 2>&1; then
      kill "$child_pid" >/dev/null 2>&1 || true
    fi
  done
  for child_pid in "${child_pids[@]:-}"; do
    wait "$child_pid" >/dev/null 2>&1 || true
  done
}

trap stop_children EXIT INT TERM
cd "$repository_root"

echo "Starting ComfyGallery development services:"
echo "  Web: http://127.0.0.1:5173"
echo "  API: http://127.0.0.1:8000"
echo "Press Ctrl-C to stop API, worker, and web. PostgreSQL/Redis remain available."

"$environment_runner" \
  uv run --package comfy-gallery-api \
  uvicorn comfy_gallery_api.main:app \
  --reload --host 127.0.0.1 --port 8000 &
child_pids+=("$!")

"$environment_runner" \
  uv run --package comfy-gallery-worker \
  dramatiq --processes 1 --threads 1 --watch . comfy_gallery_worker.tasks &
child_pids+=("$!")

pnpm --filter @comfy-gallery/web dev -- --host 127.0.0.1 &
child_pids+=("$!")

while true; do
  for child_pid in "${child_pids[@]}"; do
    if ! kill -0 "$child_pid" >/dev/null 2>&1; then
      wait "$child_pid"
      exit $?
    fi
  done
  sleep 1
done
