#!/bin/sh
set -eu

platform="${CG_SECURITY_SCAN_PLATFORM:-linux/amd64}"
trivy_image="${CG_TRIVY_IMAGE:-aquasec/trivy:0.72.0@sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f}"
scan_root="${TMPDIR:-/tmp}"
project_version="$(tr -d '[:space:]' < VERSION)"

if [ -z "$project_version" ]; then
    echo "VERSION is empty." >&2
    exit 1
fi

case "$scan_root" in
    /*) ;;
    *)
        echo "TMPDIR must be an absolute path." >&2
        exit 1
        ;;
esac

scan_dir="$(mktemp -d "$scan_root/comfy-gallery-security.XXXXXX")"
tag_suffix="scan-$$"
backend_image="comfy-gallery-security-backend:$tag_suffix"
web_image="comfy-gallery-security-web:$tag_suffix"
backup_image="comfy-gallery-security-backup:$tag_suffix"
database_image="comfy-gallery-security-database:$tag_suffix"
redis_image="comfy-gallery-security-redis:$tag_suffix"

cleanup() {
    docker image rm \
        "$backend_image" \
        "$web_image" \
        "$backup_image" \
        "$database_image" \
        "$redis_image" >/dev/null 2>&1 || true
    case "$scan_dir" in
        "$scan_root"/comfy-gallery-security.*)
            rm -rf -- "$scan_dir"
            ;;
    esac
}
trap cleanup EXIT INT TERM

docker buildx build \
    --platform "$platform" \
    --pull \
    --load \
    --build-arg "CG_PROJECT_VERSION=$project_version" \
    --tag "$backend_image" \
    --file deploy/docker/backend.Dockerfile \
    .
docker buildx build \
    --platform "$platform" \
    --pull \
    --load \
    --build-arg "CG_PROJECT_VERSION=$project_version" \
    --tag "$web_image" \
    --file deploy/docker/web.Dockerfile \
    .
docker buildx build \
    --platform "$platform" \
    --pull \
    --load \
    --build-arg "CG_PROJECT_VERSION=$project_version" \
    --tag "$backup_image" \
    --file deploy/docker/backup.Dockerfile \
    .
docker buildx build \
    --platform "$platform" \
    --pull \
    --load \
    --build-arg "CG_PROJECT_VERSION=$project_version" \
    --tag "$database_image" \
    --file deploy/docker/database.Dockerfile \
    .
docker buildx build \
    --platform "$platform" \
    --pull \
    --load \
    --build-arg "CG_PROJECT_VERSION=$project_version" \
    --tag "$redis_image" \
    --file deploy/docker/redis.Dockerfile \
    .

docker save --output "$scan_dir/backend.tar" "$backend_image"
docker save --output "$scan_dir/web.tar" "$web_image"
docker save --output "$scan_dir/backup.tar" "$backup_image"
docker save --output "$scan_dir/database.tar" "$database_image"
docker save --output "$scan_dir/redis.tar" "$redis_image"
mkdir "$scan_dir/cache"

for artifact in backend web backup database redis; do
    echo "Scanning $artifact image for high and critical vulnerabilities..."
    docker run --rm \
        --volume "$scan_dir:/scan" \
        "$trivy_image" image \
        --cache-dir /scan/cache \
        --scanners vuln \
        --severity HIGH,CRITICAL \
        --exit-code 1 \
        --input "/scan/$artifact.tar"
done
