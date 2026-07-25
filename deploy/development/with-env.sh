#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
environment_file="${CG_DEV_ENV_FILE:-$repository_root/.env.development}"

if [[ ! -f "$environment_file" ]]; then
  echo "Missing $environment_file. Run 'make dev-bootstrap' first." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$environment_file"
set +a

cd "$repository_root"
exec "$@"
