from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/prepare_release.py"
VERSION = "0.1.0-rc.34"
NEXT_VERSION = "0.1.0-rc.35"

DOCKERFILES = (
    "backend.Dockerfile",
    "backup.Dockerfile",
    "database.Dockerfile",
    "redis.Dockerfile",
    "web.Dockerfile",
    "web-overlay.Dockerfile",
)


def _fixture_files() -> dict[str, str]:
    files = {
        "VERSION": f"{VERSION}\n",
        "pyproject.toml": f'[project]\nname = "root"\nversion = "{VERSION}"\n',
        "package.json": (
            f'{{\n  "name": "root",\n  "version": "{VERSION}",\n  "private": true\n}}\n'
        ),
        "apps/web/package.json": (
            f'{{\n  "name": "web",\n  "version": "{VERSION}",\n  "private": true\n}}\n'
        ),
        "compose.yaml": (
            "services:\n"
            "  api:\n"
            "    image: ${CG_IMAGE_NAMESPACE:-project-comfy-gallery}/backend:"
            f"${{CG_IMAGE_TAG:-{VERSION}}}\n"
            "    environment:\n"
            f"      CG_PROJECT_VERSION: ${{CG_IMAGE_TAG:-{VERSION}}}\n"
        ),
        "README.md": (
            f"The locked release candidate is `{VERSION}`. Runtime images use the same tag.\n"
        ),
        "CHANGELOG.md": (
            "# Changelog\n\n"
            "## Unreleased\n\n"
            "- Fixed the heatmap pointer offset.\n\n"
            f"## {VERSION} — 2026-01-01\n\n"
            "- Previous release.\n"
        ),
    }
    for relative_path in (
        "apps/api/pyproject.toml",
        "apps/worker/pyproject.toml",
        "packages/py/core/pyproject.toml",
    ):
        files[relative_path] = f'[project]\nname = "pkg"\nversion = "{VERSION}"\n'
    for relative_path in (
        "apps/api/src/comfy_gallery_api/__init__.py",
        "apps/worker/src/comfy_gallery_worker/__init__.py",
        "packages/py/core/src/comfy_gallery_core/__init__.py",
    ):
        files[relative_path] = f'__version__ = "{VERSION}"\n'
    for name in DOCKERFILES:
        files[f"deploy/docker/{name}"] = f"ARG CG_PROJECT_VERSION={VERSION}\n"
    return files


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True,
        capture_output=True,
        check=True,
    )


def _make_repository(root: Path) -> None:
    for relative_path, contents in _fixture_files().items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "release-test@example.test")
    _git(root, "config", "user.name", "Release Test")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "fixture")


def _run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )


def _load_module() -> object:
    specification = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def test_next_version_derives_release_candidates_and_stable_bumps() -> None:
    module = _load_module()

    assert module.next_version("0.1.0-rc.34", "rc") == "0.1.0-rc.35"
    assert module.next_version("0.1.0", "rc") == "0.1.1-rc.1"
    assert module.next_version("0.1.0-rc.34", "patch") == "0.1.1"
    assert module.next_version("0.1.0-rc.34", "minor") == "0.2.0"
    assert module.next_version("0.1.0-rc.34", "major") == "1.0.0"
    with pytest.raises(module.ReleaseError, match="unsupported prerelease"):
        module.next_version("0.1.0-beta.2", "rc")


def test_prepare_release_rewrites_every_version_location(tmp_path: Path) -> None:
    _make_repository(tmp_path)

    result = _run(tmp_path, "--bump", "rc", "--skip-openapi", "--skip-check")

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == NEXT_VERSION
    compose = (tmp_path / "compose.yaml").read_text(encoding="utf-8")
    assert compose.count(f"CG_IMAGE_TAG:-{NEXT_VERSION}") == 2
    assert VERSION not in compose
    assert (tmp_path / "deploy/docker/web.Dockerfile").read_text(
        encoding="utf-8"
    ).strip() == f"ARG CG_PROJECT_VERSION={NEXT_VERSION}"
    assert (tmp_path / "apps/web/package.json").read_text(encoding="utf-8").splitlines()[
        2
    ].strip() == f'"version": "{NEXT_VERSION}",'
    assert f"`{NEXT_VERSION}`" in (tmp_path / "README.md").read_text(encoding="utf-8")

    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## {NEXT_VERSION} — {date.today().isoformat()}" in changelog
    assert changelog.index("## Unreleased") < changelog.index(f"## {NEXT_VERSION} —")
    assert "- Fixed the heatmap pointer offset." in changelog

    status = _git(tmp_path, "status", "--porcelain").stdout
    assert "VERSION" in status
    assert "CHANGELOG.md" in status


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    _make_repository(tmp_path)

    result = _run(tmp_path, "--bump", "rc", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert "Dry run: no files were written" in result.stdout
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == VERSION


def test_dirty_worktree_is_refused(tmp_path: Path) -> None:
    _make_repository(tmp_path)
    (tmp_path / "README.md").write_text("uncommitted\n", encoding="utf-8")

    result = _run(tmp_path, "--bump", "rc", "--skip-openapi", "--skip-check")

    assert result.returncode == 1
    assert "worktree must be clean" in result.stderr
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == VERSION


def test_empty_unreleased_section_is_refused(tmp_path: Path) -> None:
    _make_repository(tmp_path)
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## Unreleased\n\n## {VERSION} — 2026-01-01\n\n- Previous release.\n",
        encoding="utf-8",
    )
    _git(tmp_path, "commit", "-qam", "empty unreleased")

    result = _run(tmp_path, "--bump", "rc", "--skip-openapi", "--skip-check")

    assert result.returncode == 1
    assert "no entries to release" in result.stderr
    assert (tmp_path / "VERSION").read_text(encoding="utf-8").strip() == VERSION


def test_existing_tag_is_refused(tmp_path: Path) -> None:
    _make_repository(tmp_path)
    _git(tmp_path, "tag", f"v{NEXT_VERSION}")

    result = _run(tmp_path, "--bump", "rc", "--skip-openapi", "--skip-check")

    assert result.returncode == 1
    assert "already exists" in result.stderr
