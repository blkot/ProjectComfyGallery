#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repository_root"

for command_name in uv pnpm docker ffmpeg ffprobe; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required development command is missing: $command_name" >&2
    exit 1
  fi
done

if [[ ! -f .env.development ]]; then
  cp .env.development.example .env.development
  echo "Created .env.development with isolated local-only defaults."
fi

mkdir -p \
  data/development/managed \
  data/development/staging \
  data/development/exports \
  data/development/backups \
  data/development/runtime \
  data/development/import

uv sync --frozen --all-packages
pnpm install --frozen-lockfile

echo "Mac development dependencies and directories are ready."
