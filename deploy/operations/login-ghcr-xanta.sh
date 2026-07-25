#!/usr/bin/env bash

set -Eeuo pipefail

nas_helper="${XANTA_NAS_HELPER:-$HOME/.local/bin/xanta-nas}"
github_username="${GITHUB_USERNAME:-blkot}"

if [[ ! -x "$nas_helper" ]]; then
  echo "NAS helper is not executable: $nas_helper" >&2
  exit 1
fi

echo "GitHub requires a classic personal access token with read:packages for a"
echo "non-Actions Docker client pulling private GHCR images."
read -r -s -p "GHCR token for ${github_username}: " ghcr_token
echo

if [[ -z "$ghcr_token" ]]; then
  echo "No token supplied." >&2
  exit 1
fi

printf '%s' "$ghcr_token" |
  "$nas_helper" docker login ghcr.io --username "$github_username" --password-stdin
unset ghcr_token

echo "The Xanta NAS Docker daemon is authenticated to GHCR."
