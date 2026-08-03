from __future__ import annotations

import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_mac_development_environment_is_isolated() -> None:
    environment = (ROOT / ".env.development.example").read_text(encoding="utf-8")
    compose = yaml.safe_load((ROOT / "compose.development.yaml").read_text(encoding="utf-8"))

    assert compose["name"] == "comfy-gallery-development"
    assert set(compose["services"]) == {"postgres", "redis"}
    assert "127.0.0.1:${DEV_POSTGRES_PORT:-55432}:5432" in compose["services"]["postgres"]["ports"]
    assert "127.0.0.1:${DEV_REDIS_PORT:-56379}:6379" in compose["services"]["redis"]["ports"]
    assert "data/development/managed" in environment
    assert "data/development/import" in environment
    assert "127.0.0.1:55432" in environment
    assert "127.0.0.1:56379" in environment
    assert "192.168.50.68" not in environment


def test_development_and_release_shell_scripts_parse_and_are_executable() -> None:
    scripts = (
        *sorted((ROOT / "deploy/development").glob("*.sh")),
        ROOT / "deploy/operations/create-milestone.sh",
        ROOT / "deploy/operations/login-ghcr-xanta.sh",
        ROOT / "deploy/operations/deploy-release.sh",
        ROOT / "deploy/operations/deploy-xanta-release.sh",
    )

    for script in scripts:
        assert os.access(script, os.X_OK), f"{script} must be executable"
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_release_workflow_publishes_locked_amd64_images() -> None:
    workflow = (ROOT / ".github/workflows/release-images.yml").read_text(encoding="utf-8")

    assert "IMAGE_ROOT: ghcr.io/blkot/project-comfy-gallery" in workflow
    assert "platforms: linux/amd64" in workflow
    assert "CG_PROJECT_VERSION=${{ needs.validate.outputs.version }}" in workflow
    assert "cache-from: type=gha,scope=${{ matrix.image }}" in workflow
    assert "cache-to: type=gha,mode=max,scope=${{ matrix.image }}" in workflow
    assert "if: ${{ github.event.repository.private == false }}" in workflow
    assert "provenance: mode=max" in workflow
    assert "sbom: true" in workflow
    assert workflow.count("dockerfile: deploy/docker/") == 5


def test_nas_deployment_pulls_without_building() -> None:
    deployment = (ROOT / "deploy/operations/deploy-release.sh").read_text(encoding="utf-8")

    assert 'docker compose "${compose_files[@]}" pull' in deployment
    assert 'docker compose "${compose_files[@]}" up -d --no-build' in deployment
    assert "docker exec comfy-gallery-backup-1 comfy-gallery-backup" in deployment
    assert "alembic -c packages/py/core/alembic.ini upgrade head" in deployment
    assert "alembic -c packages/py/core/alembic.ini check" in deployment


def test_media_jobs_have_dedicated_worker_capacity() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["worker"]["command"][-3:] == ["--queues", "system", "media"]
    assert services["worker-background"]["command"][-5:] == [
        "--queues",
        "scan",
        "workflow",
        "registry",
        "maintenance",
    ]
    assert (
        services["worker-background"]["environment"]["CG_RUNTIME_ROOT"]
        == "/data/runtime/background-worker"
    )
