#!/usr/bin/env bash

set -Eeuo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repository_root"

release_version="${1:-$(tr -d '[:space:]' < VERSION)}"
release_tag="v${release_version}"

if [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  echo "Invalid release version: $release_version" >&2
  exit 1
fi

if [[ "$(tr -d '[:space:]' < VERSION)" != "$release_version" ]]; then
  echo "VERSION does not match $release_version." >&2
  exit 1
fi

if ! grep -Fq "## ${release_version} " CHANGELOG.md; then
  echo "CHANGELOG.md must contain a dated heading for ${release_version}." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "The worktree must be clean before creating a milestone." >&2
  exit 1
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Milestones must be created from main." >&2
  exit 1
fi

git fetch origin main --tags
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]]; then
  echo "Local main must exactly match origin/main." >&2
  exit 1
fi

if git show-ref --verify --quiet "refs/tags/${release_tag}" ||
  git ls-remote --exit-code --tags origin "refs/tags/${release_tag}" >/dev/null 2>&1; then
  echo "Release tag already exists: ${release_tag}" >&2
  exit 1
fi

echo "Running the complete milestone verification suite."
make check
POSTGRES_PASSWORD=release-validation \
  CG_ADMIN_PASSWORD=release-validation \
  CG_IMAGE_TAG="$release_version" \
  docker compose -f compose.yaml -f compose.production.yaml config --quiet

git tag -a "$release_tag" -m "Project Comfy Gallery ${release_version}"
git push origin "$release_tag"

echo "Published ${release_tag}."
echo "GitHub Actions is now building immutable linux/amd64 images:"
echo "https://github.com/blkot/ProjectComfyGallery/actions/workflows/release-images.yml"
