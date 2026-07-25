#!/usr/bin/env bash

set -Eeuo pipefail

release_version="${1:-}"
confirmation="${2:-}"
release_tag="v${release_version}"
nas_helper="${XANTA_NAS_HELPER:-$HOME/.local/bin/xanta-nas}"
remote_repository="${XANTA_COMFY_GALLERY_REPOSITORY:-/share/homes/xanta/data/docker_data/ProjectComfyGallery}"

if [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  echo "Usage: $0 <release-version> [--yes]" >&2
  exit 1
fi

if [[ ! -x "$nas_helper" ]]; then
  echo "NAS helper is not executable: $nas_helper" >&2
  exit 1
fi

workflow_record="$(
  gh run list \
    --repo blkot/ProjectComfyGallery \
    --workflow release-images.yml \
    --limit 50 \
    --json headBranch,status,conclusion,url \
    --jq ".[] | select(.headBranch == \"${release_tag}\") | [.status,.conclusion,.url] | @tsv" |
    head -1
)"

if [[ -z "$workflow_record" ]]; then
  echo "No image workflow run found for ${release_tag}." >&2
  exit 1
fi

IFS=$'\t' read -r workflow_status workflow_conclusion workflow_url <<<"$workflow_record"
if [[ "$workflow_status" != "completed" || "$workflow_conclusion" != "success" ]]; then
  echo "Release images are not ready: ${workflow_status}/${workflow_conclusion}" >&2
  echo "$workflow_url" >&2
  exit 1
fi

if [[ "$confirmation" != "--yes" ]]; then
  read -r -p "Deploy ${release_version} to the production Xanta NAS? Type the version: " answer
  if [[ "$answer" != "$release_version" ]]; then
    echo "Deployment cancelled." >&2
    exit 1
  fi
fi

"$nas_helper" sh -lc "
  set -eu
  cd '$remote_repository'
  test -z \"\$(/opt/bin/git status --porcelain)\"
  /opt/bin/git fetch --tags origin
  /opt/bin/git checkout --detach '$release_tag'
  ./deploy/operations/deploy-release.sh '$release_version'
"

echo "Deployment completed from ${workflow_url}"
