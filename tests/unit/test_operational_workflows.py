from __future__ import annotations

import json
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
        ROOT / "deploy/operations/deploy-web-only.sh",
        ROOT / "deploy/operations/deploy-xanta-auto.sh",
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
    assert 'docker compose "${compose_files[@]}" run --rm --no-deps backup run' in deployment
    assert "--entrypoint sh backup" in deployment
    assert "alembic -c packages/py/core/alembic.ini upgrade head" in deployment
    assert "alembic -c packages/py/core/alembic.ini check" in deployment
    assert "comfy-gallery-worker-background-1" in deployment
    assert "comfy-gallery-worker-spatial-1" in deployment


def test_nas_release_confirmation_accepts_crlf_terminal_input(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_gh = fake_bin / "gh"
    fake_gh.write_text(
        "#!/usr/bin/env bash\nprintf '123\\tcompleted\\tsuccess\\thttps://example.test/release-run\\n'\n",
        encoding="utf-8",
    )
    fake_gh.chmod(0o755)

    version = "0.1.0-rc.24"
    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"
    environment["XANTA_NAS_HELPER"] = "/usr/bin/true"

    result = subprocess.run(
        [str(ROOT / "deploy/operations/deploy-xanta-release.sh"), version],
        input=f"{version}\r\n",
        text=True,
        capture_output=True,
        env=environment,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Deployment completed from https://example.test/release-run" in result.stdout


def test_backup_retention_warning_does_not_invalidate_a_verified_dump(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_commands = {
        "pg_dump": """#!/bin/sh
for argument in "$@"; do
  case "$argument" in
    --file=*) output=${argument#--file=} ;;
  esac
done
printf 'verified-dump' > "$output"
""",
        "pg_restore": "#!/bin/sh\nexit 0\n",
        "psql": "#!/bin/sh\nprintf '0012_workflow_input_media\\n'\n",
        "stat": "#!/bin/sh\n/usr/bin/wc -c < \"$3\" | tr -d ' ' | tr -d '\\n'\n",
    }
    for name, content in fake_commands.items():
        command = fake_bin / name
        command.write_text(content, encoding="utf-8")
        command.chmod(0o755)

    backup_root = tmp_path / "backups"
    protected = backup_root / "daily" / "cg-20000101T000000Z"
    protected.mkdir(parents=True)
    (protected / "database.dump").write_bytes(b"legacy")
    protected.chmod(0o500)
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "CG_BACKUP_ROOT": str(backup_root),
            "CG_BACKUP_DAILY_KEEP": "1",
            "CG_BACKUP_WEEKLY_KEEP": "1",
        }
    )

    try:
        result = subprocess.run(
            ["sh", str(ROOT / "deploy/operations/backup.sh")],
            text=True,
            capture_output=True,
            env=environment,
            check=False,
        )
    finally:
        protected.chmod(0o700)

    assert result.returncode == 0, result.stderr
    status = json.loads((backup_root / ".backup-status.json").read_text(encoding="utf-8"))
    assert status["status"] == "ok"
    assert status["retention_warning"] is True
    assert "could not prune" in result.stderr


def test_auto_deployer_offers_one_command_release_shipping() -> None:
    deployment = (ROOT / "deploy/operations/deploy-xanta-auto.sh").read_text(encoding="utf-8")

    assert "plan | auto | web | release | ship | status" in deployment
    assert '"$milestone_creator" "$release_version"' in deployment
    assert "deploy/operations/backup.sh" in deployment


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
    assert services["worker-spatial"]["command"][-2:] == ["--queues", "spatial"]
    assert (
        services["worker-spatial"]["environment"]["CG_RUNTIME_ROOT"]
        == "/data/runtime/spatial-worker"
    )
