#!/usr/bin/env bash

set -Eeuo pipefail
umask 077

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
nas_helper="${XANTA_NAS_HELPER:-${HOME}/.local/bin/xanta-nas}"
remote_repository="${XANTA_COMFY_GALLERY_REPOSITORY:-/share/homes/xanta/data/docker_data/ProjectComfyGallery}"

operation="plan"
from_revision=""
target_revision="HEAD"
release_version=""
assume_yes=false
dry_run=false
keep_context=false
include_worktree=true

usage() {
  cat <<'EOF'
Usage: deploy/operations/deploy-xanta-auto.sh [operation] [options]

Inspect the current Xanta NAS deployment, classify local changes, and choose the
smallest safe deployment path.

Operations:
  plan       Show the detected NAS baselines, changed files, and deployment plan.
             This is the default and never changes the NAS.
  auto       Execute the detected plan after confirmation.
  web        Require a web-only change and run the targeted web deployment.
  release    Deploy an existing immutable release tag through the standard backup,
             migration, service replacement, and health-check workflow.
  status     Show the repository and Compose state currently running on the NAS.

Options:
  --from REF             Override both auto-detected deployed revision baselines.
  --to REF               Classify up to REF (default: HEAD).
  --release-version VER  Immutable release to use for a release deployment. When
                         omitted, VERSION is used and still must tag --to exactly.
  --committed-only       Ignore staged, unstaged, and untracked local files.
  --dry-run              Verify/build the selected path without changing the NAS.
  --keep-context         Keep the web-only NAS staging directory for diagnosis.
  --yes                  Skip the delegated deployment confirmation.
  -h, --help             Show this help.

Classification:
  none     Documentation, tests, agent files, mobile, XR, or operations-only work.
  web      React/web inputs only; recreates only the web container.
  release  Backend/API/worker/shared Python, migrations, dependencies, Docker,
           Compose, environment contracts, or mixed/unknown runtime changes.

Examples:
  ./deploy/operations/deploy-xanta-auto.sh plan
  ./deploy/operations/deploy-xanta-auto.sh auto --dry-run
  ./deploy/operations/deploy-xanta-auto.sh auto --yes
  ./deploy/operations/deploy-xanta-auto.sh release --release-version 0.1.0-rc.15

Environment overrides:
  XANTA_NAS_HELPER
  XANTA_COMFY_GALLERY_REPOSITORY
EOF
}

die() {
  echo "Error: $*" >&2
  exit 1
}

if (($# > 0)) && [[ "$1" != -* ]]; then
  operation="$1"
  shift
fi

while (($# > 0)); do
  case "$1" in
    --from)
      (($# >= 2)) || die "--from requires a Git revision"
      from_revision="$2"
      shift
      ;;
    --to)
      (($# >= 2)) || die "--to requires a Git revision"
      target_revision="$2"
      shift
      ;;
    --release-version)
      (($# >= 2)) || die "--release-version requires a version"
      release_version="$2"
      shift
      ;;
    --committed-only)
      include_worktree=false
      ;;
    --dry-run)
      dry_run=true
      ;;
    --keep-context)
      keep_context=true
      ;;
    --yes)
      assume_yes=true
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1"
      ;;
  esac
  shift
done

case "$operation" in
  plan | auto | web | release | status) ;;
  *) die "unknown operation: $operation" ;;
esac

cd "$repository_root"

command -v git >/dev/null 2>&1 || die "git is required"
[[ -x "$nas_helper" ]] || die "NAS helper is not executable: $nas_helper"
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a Git worktree"

target_commit="$(git rev-parse --verify "${target_revision}^{commit}")" ||
  die "target is not a commit: $target_revision"
head_commit="$(git rev-parse --verify HEAD)"

remote_checkout_commit="$(
  "$nas_helper" sh -c '
    repository="$1"
    cd "$repository"
    /opt/bin/git rev-parse HEAD
  ' -- "$remote_repository"
)"
remote_checkout_description="$(
  "$nas_helper" sh -c '
    repository="$1"
    cd "$repository"
    /opt/bin/git describe --tags --always --dirty
  ' -- "$remote_repository"
)"

remote_service_revision() {
  local container_name="$1"
  "$nas_helper" docker inspect "$container_name" \
    --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' 2>/dev/null || true
}

api_image_revision="$(remote_service_revision comfy-gallery-api-1)"
web_image_revision="$(remote_service_revision comfy-gallery-web-1)"

resolve_deployed_commit() {
  local recorded_revision="$1"
  local candidate=""
  local candidate_commit=""
  local resolved=""

  resolved="$(git rev-parse --verify "${recorded_revision}^{commit}" 2>/dev/null || true)"
  if [[ -n "$resolved" ]]; then
    printf '%s\n' "$resolved"
    return
  fi

  while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    candidate_commit="$(git rev-parse --verify "${candidate}^{commit}" 2>/dev/null || true)"
    if [[ -n "$candidate_commit" ]]; then
      resolved="$candidate_commit"
    fi
  done < <(printf '%s\n' "$recorded_revision" | grep -Eo '[0-9a-fA-F]{7,40}' || true)

  if [[ -n "$resolved" ]]; then
    printf '%s\n' "$resolved"
  fi
}

if [[ -n "$from_revision" ]]; then
  baseline_commit="$(git rev-parse --verify "${from_revision}^{commit}")" ||
    die "baseline is not a commit: $from_revision"
  api_baseline="$baseline_commit"
  web_baseline="$baseline_commit"
  api_baseline_source="override ${from_revision}"
  web_baseline_source="override ${from_revision}"
else
  api_baseline="$(resolve_deployed_commit "$api_image_revision")"
  web_baseline="$(resolve_deployed_commit "$web_image_revision")"
  if [[ -z "$api_baseline" ]]; then
    api_baseline="$remote_checkout_commit"
    api_baseline_source="NAS checkout fallback"
  else
    api_baseline_source="${api_image_revision:-image label}"
  fi
  if [[ -z "$web_baseline" ]]; then
    web_baseline="$remote_checkout_commit"
    web_baseline_source="NAS checkout fallback"
  else
    web_baseline_source="${web_image_revision:-image label}"
  fi
fi

show_status() {
  echo "Xanta NAS deployment"
  echo "  checkout:       ${remote_checkout_description} (${remote_checkout_commit:0:12})"
  echo "  API revision:   ${api_image_revision:-unknown}"
  echo "  Web revision:   ${web_image_revision:-unknown}"
  echo
  "$nas_helper" sh -c '
    repository="$1"
    cd "$repository"
    docker compose -f compose.yaml -f compose.production.yaml ps
  ' -- "$remote_repository"
}

if [[ "$operation" == "status" ]]; then
  show_status
  exit 0
fi

plan_directory="$(mktemp -d "${TMPDIR:-/tmp}/comfy-gallery-deploy-plan.XXXXXX")"
plan_marker="$plan_directory/.comfy-gallery-owned"
touch "$plan_marker"

cleanup_plan_directory() {
  if [[ -f "$plan_marker" ]]; then
    find "$plan_directory" -depth -delete
  fi
}
trap cleanup_plan_directory EXIT

all_changes_file="$plan_directory/all"
ignored_changes_file="$plan_directory/ignored"
web_changes_file="$plan_directory/web"
release_changes_file="$plan_directory/release"
worktree_changes_file="$plan_directory/worktree"
runtime_worktree_changes_file="$plan_directory/worktree-runtime"
: >"$all_changes_file"
: >"$ignored_changes_file"
: >"$web_changes_file"
: >"$release_changes_file"
: >"$worktree_changes_file"
: >"$runtime_worktree_changes_file"

collect_committed_changes() {
  local baseline="$1"
  git diff --name-only "$baseline" "$target_commit" -- >>"$all_changes_file"
}

collect_committed_changes "$api_baseline"
if [[ "$web_baseline" != "$api_baseline" ]]; then
  collect_committed_changes "$web_baseline"
fi

if [[ "$include_worktree" == true && "$target_commit" == "$head_commit" ]]; then
  git diff --name-only -- >>"$worktree_changes_file"
  git diff --cached --name-only -- >>"$worktree_changes_file"
  git ls-files --others --exclude-standard >>"$worktree_changes_file"
  LC_ALL=C sort -u "$worktree_changes_file" -o "$worktree_changes_file"
  cat "$worktree_changes_file" >>"$all_changes_file"
fi

LC_ALL=C sort -u "$all_changes_file" -o "$all_changes_file"

deployment_class_for_path() {
  local path="$1"
  case "$path" in
    "")
      printf '%s\n' "none"
      ;;
    doc/* | docs/* | tests/* | mobile/* | XR/* | .github/* | .openai/* | \
      deploy/operations/* | deploy/development/* | scripts/* | AGENTS.md | \
      CONTEXT-MAP.md | CHANGELOG.md | README.md | *.md)
      printf '%s\n' "none"
      ;;
    testdata/*)
      case "$path" in
        testdata/synthetic/*)
          printf '%s\n' "release"
          ;;
        *)
          printf '%s\n' "none"
          ;;
      esac
      ;;
    apps/web/*.test.ts | apps/web/*.test.tsx | apps/web/*.spec.ts | apps/web/*.spec.tsx)
      printf '%s\n' "none"
      ;;
    apps/web/* | package.json | pnpm-lock.yaml | pnpm-workspace.yaml | \
      deploy/docker/nginx.conf | deploy/docker/web-overlay.Dockerfile)
      printf '%s\n' "web"
      ;;
    *)
      printf '%s\n' "release"
      ;;
  esac
}

classify_path() {
  local path="$1"
  local deployment_class=""
  deployment_class="$(deployment_class_for_path "$path")"
  case "$deployment_class" in
    none)
      [[ -z "$path" ]] || printf '%s\n' "$path" >>"$ignored_changes_file"
      ;;
    web)
      printf '%s\n' "$path" >>"$web_changes_file"
      ;;
    release)
      printf '%s\n' "$path" >>"$release_changes_file"
      ;;
    *)
      die "internal classification error for ${path}"
      ;;
  esac
}

while IFS= read -r changed_path; do
  classify_path "$changed_path"
done <"$all_changes_file"

while IFS= read -r changed_path; do
  if [[ "$(deployment_class_for_path "$changed_path")" != "none" ]]; then
    printf '%s\n' "$changed_path" >>"$runtime_worktree_changes_file"
  fi
done <"$worktree_changes_file"

ignored_count="$(wc -l <"$ignored_changes_file" | tr -d '[:space:]')"
web_count="$(wc -l <"$web_changes_file" | tr -d '[:space:]')"
release_count="$(wc -l <"$release_changes_file" | tr -d '[:space:]')"
runtime_worktree_count="$(
  wc -l <"$runtime_worktree_changes_file" | tr -d '[:space:]'
)"

if ((release_count > 0)); then
  detected_plan="release"
elif ((web_count > 0)); then
  detected_plan="web"
else
  detected_plan="none"
fi

print_file_group() {
  local label="$1"
  local file="$2"
  local count="$3"
  if ((count == 0)); then
    return
  fi
  echo "  ${label} (${count}):"
  sed 's/^/    - /' "$file"
}

echo "Deployment plan"
echo "  NAS checkout:  ${remote_checkout_description} (${remote_checkout_commit:0:12})"
echo "  API baseline:  ${api_baseline:0:12} from ${api_baseline_source}"
echo "  Web baseline:  ${web_baseline:0:12} from ${web_baseline_source}"
echo "  Target:        ${target_revision} (${target_commit:0:12})"
echo "  Worktree:      $([[ "$include_worktree" == true ]] && echo included || echo ignored)"
echo "  Result:        ${detected_plan}"
echo
print_file_group "No NAS deployment" "$ignored_changes_file" "$ignored_count"
print_file_group "Web runtime" "$web_changes_file" "$web_count"
print_file_group "Full release" "$release_changes_file" "$release_count"

if [[ "$operation" == "plan" ]]; then
  exit 0
fi

selected_plan="$detected_plan"
if [[ "$operation" == "web" ]]; then
  if ((release_count > 0)); then
    die "web-only deployment is unsafe because full-release files changed"
  fi
  selected_plan="web"
elif [[ "$operation" == "release" ]]; then
  selected_plan="release"
fi

if [[ "$selected_plan" == "none" ]]; then
  echo
  echo "No server runtime changed; the NAS was not modified."
  exit 0
fi

if [[ "$selected_plan" == "web" ]]; then
  web_deployer="$repository_root/deploy/operations/deploy-web-only.sh"
  [[ "$target_commit" == "$head_commit" ]] ||
    die "web-only deployment builds the current worktree; --to must resolve to HEAD"
  [[ -x "$web_deployer" ]] ||
    die "targeted web deployer is unavailable or not executable: $web_deployer"

  web_arguments=()
  if [[ "$assume_yes" == true ]]; then
    web_arguments+=(--yes)
  fi
  if [[ "$dry_run" == true ]]; then
    web_arguments+=(--dry-run)
  fi
  if [[ "$keep_context" == true ]]; then
    web_arguments+=(--keep-context)
  fi

  echo
  echo "Delegating to the isolated web-only deployment."
  "$web_deployer" "${web_arguments[@]}"
  exit 0
fi

if [[ -z "$release_version" ]]; then
  release_version="$(tr -d '[:space:]' < VERSION)"
fi
if [[ ! "$release_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]]; then
  die "invalid release version: $release_version"
fi
if [[ "$(tr -d '[:space:]' < VERSION)" != "$release_version" ]]; then
  die "VERSION does not match requested release ${release_version}"
fi

release_tag="v${release_version}"
git fetch --quiet origin --tags
release_commit="$(git rev-parse --verify "${release_tag}^{commit}" 2>/dev/null || true)"
if [[ -z "$release_commit" ]]; then
  die "${release_tag} does not exist; finalize VERSION/CHANGELOG and create the milestone first"
fi
if [[ "$release_commit" != "$target_commit" ]]; then
  die "${release_tag} points to ${release_commit:0:12}, not target ${target_commit:0:12}"
fi
if [[ "$include_worktree" == true ]] && ((runtime_worktree_count > 0)); then
  echo "Uncommitted runtime files cannot be included in an immutable release:" >&2
  sed 's/^/  - /' "$runtime_worktree_changes_file" >&2
  die "commit or remove the runtime changes, or use --committed-only intentionally"
fi

release_deployer="$repository_root/deploy/operations/deploy-xanta-release.sh"
[[ -x "$release_deployer" ]] || die "release deployer is unavailable: $release_deployer"

if [[ "$dry_run" == true ]]; then
  command -v gh >/dev/null 2>&1 || die "gh is required for release verification"
  workflow_record="$(
    gh run list \
      --repo blkot/ProjectComfyGallery \
      --workflow release-images.yml \
      --limit 50 \
      --json headBranch,status,conclusion,url \
      --jq ".[] | select(.headBranch == \"${release_tag}\") | [.status,.conclusion,.url] | @tsv" |
      head -1
  )"
  [[ -n "$workflow_record" ]] || die "no release-image workflow found for ${release_tag}"
  echo
  echo "Release dry run complete: ${workflow_record}"
  echo "The NAS was not modified."
  exit 0
fi

release_arguments=("$release_version")
if [[ "$assume_yes" == true ]]; then
  release_arguments+=(--yes)
fi

echo
echo "Delegating to the immutable release deployment."
"$release_deployer" "${release_arguments[@]}"
