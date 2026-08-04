from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from comfy_gallery_api import __version__ as api_version
from comfy_gallery_core import __version__ as core_version
from comfy_gallery_worker import __version__ as worker_version

ROOT = Path(__file__).resolve().parents[2]
PYPROJECTS = (
    ROOT / "pyproject.toml",
    ROOT / "apps/api/pyproject.toml",
    ROOT / "apps/worker/pyproject.toml",
    ROOT / "packages/py/core/pyproject.toml",
)
PACKAGE_JSON_FILES = (
    ROOT / "package.json",
    ROOT / "apps/web/package.json",
)
RELEASE_DOCKERFILES = tuple(
    ROOT / "deploy/docker" / name
    for name in (
        "backend.Dockerfile",
        "backup.Dockerfile",
        "database.Dockerfile",
        "redis.Dockerfile",
        "web.Dockerfile",
    )
)
WEB_OVERLAY_DOCKERFILE = ROOT / "deploy/docker/web-overlay.Dockerfile"


def test_release_version_is_consistent() -> None:
    release_version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

    assert release_version == "0.1.0-rc.14"
    assert {api_version, core_version, worker_version} == {release_version}
    for path in PYPROJECTS:
        with path.open("rb") as handle:
            assert tomllib.load(handle)["project"]["version"] == release_version
    for path in PACKAGE_JSON_FILES:
        assert json.loads(path.read_text(encoding="utf-8"))["version"] == release_version

    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    for image in ("backend", "web", "backup", "postgres", "redis"):
        assert (
            "${CG_IMAGE_NAMESPACE:-project-comfy-gallery}/"
            f"{image}:${{CG_IMAGE_TAG:-{release_version}}}"
        ) in compose


def test_runtime_base_images_are_digest_pinned() -> None:
    digest_pattern = re.compile(r"^FROM\s+\S+@sha256:[0-9a-f]{64}(?:\s+AS\s+\S+)?$")

    assert len(RELEASE_DOCKERFILES) == 5
    for dockerfile in RELEASE_DOCKERFILES:
        contents = dockerfile.read_text(encoding="utf-8")
        from_lines = [line for line in contents.splitlines() if line.startswith("FROM ")]
        assert from_lines
        assert all(digest_pattern.fullmatch(line) for line in from_lines)
        assert f"ARG CG_PROJECT_VERSION={release_version()}" in contents
        assert 'org.opencontainers.image.version="$CG_PROJECT_VERSION"' in contents
        assert 'org.opencontainers.image.source="$CG_SOURCE_URL"' in contents
        assert 'org.opencontainers.image.revision="$CG_REVISION"' in contents


def test_web_overlay_uses_the_injected_running_image() -> None:
    contents = WEB_OVERLAY_DOCKERFILE.read_text(encoding="utf-8")

    assert "ARG BASE_IMAGE\nFROM ${BASE_IMAGE}" in contents
    assert f"ARG CG_PROJECT_VERSION={release_version()}" in contents
    assert 'org.opencontainers.image.version="$CG_PROJECT_VERSION"' in contents
    assert 'org.opencontainers.image.source="$CG_SOURCE_URL"' in contents
    assert 'org.opencontainers.image.revision="$CG_REVISION"' in contents


def test_backend_runtime_accepts_extended_spatial_projection_metadata() -> None:
    contents = (ROOT / "deploy/docker/backend.Dockerfile").read_text(encoding="utf-8")

    assert "python:3.13-alpine3.24@sha256:" in contents
    assert "testdata/synthetic/ffmpeg-extended-proj.mov.b64" in contents
    assert "ffprobe -v error -show_format -show_streams -of json" in contents


def release_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()
