#!/usr/bin/env bash

set -Eeuo pipefail

nas_helper="${XANTA_NAS_HELPER:-$HOME/.local/bin/xanta-nas}"
remote_repository="${XANTA_COMFY_GALLERY_REPOSITORY:-/share/homes/xanta/data/docker_data/ProjectComfyGallery}"
release_version=""
assume_yes=false
wait_for_images=true
wait_timeout_seconds="${CG_RELEASE_WAIT_TIMEOUT_SECONDS:-2700}"
poll_seconds="${CG_RELEASE_POLL_SECONDS:-10}"

usage() {
  cat <<'EOF'
Usage: deploy/operations/deploy-xanta-release.sh <release-version> [options]

Wait for the matching GitHub Actions image build, then deploy the immutable
release to the Xanta NAS.

Options:
  --yes                   Skip the exact-version deployment confirmation.
  --no-wait               Fail instead of waiting when images are not ready.
  --wait-timeout SECONDS  Maximum image-build wait (default: 2700).
  -h, --help              Show this help.
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

while (($# > 0)); do
  case "$1" in
    --yes)
      assume_yes=true
      ;;
    --no-wait)
      wait_for_images=false
      ;;
    --wait-timeout)
      (($# >= 2)) || die "--wait-timeout requires a number of seconds"
      wait_timeout_seconds="$2"
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      die "unknown option: $1"
      ;;
    *)
      [[ -z "$release_version" ]] || die "only one release version may be supplied"
      release_version="$1"
      ;;
  esac
  shift
done

release_tag="v${release_version}"

if [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  usage >&2
  exit 1
fi

[[ "$wait_timeout_seconds" =~ ^[1-9][0-9]*$ ]] ||
  die "--wait-timeout must be a positive integer"
[[ "$poll_seconds" =~ ^[1-9][0-9]*$ ]] ||
  die "CG_RELEASE_POLL_SECONDS must be a positive integer"

if [[ ! -x "$nas_helper" ]]; then
  die "NAS helper is not executable: $nas_helper"
fi

command -v gh >/dev/null 2>&1 || die "gh is required"

workflow_record_for_tag() {
  gh run list \
    --repo blkot/ProjectComfyGallery \
    --workflow release-images.yml \
    --limit 50 \
    --json databaseId,headBranch,status,conclusion,url \
    --jq ".[] | select(.headBranch == \"${release_tag}\") | [.databaseId,.status,.conclusion,.url] | @tsv" |
    head -1
}

deadline=$((SECONDS + wait_timeout_seconds))
last_report=""
workflow_url=""
while true; do
  workflow_record="$(workflow_record_for_tag)"
  workflow_id=""
  workflow_status="not-found"
  workflow_conclusion=""
  workflow_url=""
  if [[ -n "$workflow_record" ]]; then
    IFS=$'\t' read -r workflow_id workflow_status workflow_conclusion workflow_url \
      <<<"$workflow_record"
  fi

  report="${workflow_status}/${workflow_conclusion:-pending}"
  if [[ "$report" != "$last_report" ]]; then
    echo "Release images for ${release_tag}: ${report}"
    [[ -z "$workflow_url" ]] || echo "$workflow_url"
    last_report="$report"
  fi

  if [[ "$workflow_status" == "completed" ]]; then
    [[ "$workflow_conclusion" == "success" ]] ||
      die "release image workflow finished with ${workflow_conclusion:-unknown}"
    break
  fi
  [[ "$wait_for_images" == true ]] ||
    die "release images are not ready; rerun without --no-wait after the workflow succeeds"
  ((SECONDS < deadline)) ||
    die "timed out waiting ${wait_timeout_seconds}s for ${release_tag} images"
  sleep "$poll_seconds"
done

if [[ "$assume_yes" != true ]]; then
  read -r -p "Deploy ${release_version} to the production Xanta NAS? Type the version: " answer
  answer="${answer%$'\r'}"
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
