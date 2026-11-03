#!/usr/bin/env python3
"""Prepare a release by locking one version everywhere and promoting the changelog.

The script rewrites every version location, regenerates the committed OpenAPI
snapshot, verifies that only release files changed, and runs the full check suite.
It never commits, tags, pushes, or deploys; those remain explicit steps.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

RELEASE_VERSION_PATTERN = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?$"
)
RC_PRERELEASE_PATTERN = re.compile(r"^rc\.(?P<number>[0-9]+)$")

PYPROJECT_PATHS = (
    "pyproject.toml",
    "apps/api/pyproject.toml",
    "apps/worker/pyproject.toml",
    "packages/py/core/pyproject.toml",
)
PACKAGE_JSON_PATHS = ("package.json", "apps/web/package.json")
INIT_PATHS = (
    "apps/api/src/comfy_gallery_api/__init__.py",
    "apps/worker/src/comfy_gallery_worker/__init__.py",
    "packages/py/core/src/comfy_gallery_core/__init__.py",
)
DOCKERFILE_PATHS = tuple(
    f"deploy/docker/{name}"
    for name in (
        "backend.Dockerfile",
        "backup.Dockerfile",
        "database.Dockerfile",
        "redis.Dockerfile",
        "web.Dockerfile",
        "web-overlay.Dockerfile",
    )
)
OPENAPI_PATH = "doc/interfaces/openapi.json"


class ReleaseError(RuntimeError):
    """A precondition or verification step failed."""


@dataclass(frozen=True)
class Change:
    path: Path
    before: str
    after: str


@dataclass(frozen=True)
class ReleasePlan:
    root: Path
    current_version: str
    target_version: str
    changes: list[Change]

    @property
    def rewritten_paths(self) -> list[str]:
        return [str(change.path.relative_to(self.root)) for change in self.changes]


def parse_version(value: str) -> re.Match[str]:
    match = RELEASE_VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ReleaseError(f"not a release version: {value!r}")
    return match


def next_version(current: str, bump: str) -> str:
    """Return the version to lock for the requested bump."""

    match = parse_version(current)
    major = int(match["major"])
    minor = int(match["minor"])
    patch = int(match["patch"])
    prerelease = match["prerelease"]

    if bump == "rc":
        if prerelease is None:
            return f"{major}.{minor}.{patch + 1}-rc.1"
        rc_match = RC_PRERELEASE_PATTERN.fullmatch(prerelease)
        if rc_match is None:
            raise ReleaseError(
                f"cannot bump {current!r} to a release candidate: unsupported prerelease"
            )
        return f"{major}.{minor}.{patch}-rc.{int(rc_match['number']) + 1}"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "major":
        return f"{major + 1}.0.0"
    raise ReleaseError(f"unsupported bump: {bump}")


def _run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ReleaseError(
            f"git {' '.join(arguments)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _read(root: Path, relative_path: str) -> str:
    return (root / relative_path).read_text(encoding="utf-8")


def _replace_once(text: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    updated, count = pattern.subn(replacement, text)
    if count != 1:
        raise ReleaseError(f"{label}: expected exactly one version occurrence, found {count}")
    return updated


def _replace_all(text: str, pattern: re.Pattern[str], replacement: str, label: str) -> str:
    updated, count = pattern.subn(replacement, text)
    if count == 0:
        raise ReleaseError(f"{label}: no version occurrence found")
    return updated


def _changelog_with_release(text: str, target_version: str, release_date: str) -> str:
    if "## Unreleased\n\n" not in text:
        raise ReleaseError(
            "CHANGELOG.md must contain an empty-line separated '## Unreleased' section"
        )
    if f"## {target_version} " in text:
        raise ReleaseError(f"CHANGELOG.md already has a heading for {target_version}")

    section_start = text.index("## Unreleased")
    section_end = text.find("\n## ", section_start + len("## Unreleased"))
    section = text[section_start:] if section_end < 0 else text[section_start:section_end]
    if not any(line.startswith("- ") for line in section.splitlines()[1:]):
        raise ReleaseError("CHANGELOG.md '## Unreleased' section has no entries to release")

    heading = f"## {target_version} — {release_date}"
    return text.replace("## Unreleased\n\n", f"## Unreleased\n\n{heading}\n\n", 1)


def build_plan(root: Path, target_version: str) -> ReleasePlan:
    parse_version(target_version)
    current_version = _read(root, "VERSION").strip()
    parse_version(current_version)
    if target_version == current_version:
        raise ReleaseError(f"target version {target_version} is already locked")

    changes: list[Change] = []

    def plan_once(relative_path: str, pattern: re.Pattern[str], replacement: str) -> None:
        before = _read(root, relative_path)
        after = _replace_once(before, pattern, replacement, relative_path)
        if before != after:
            changes.append(Change(root / relative_path, before, after))

    def plan_all(relative_path: str, pattern: re.Pattern[str], replacement: str) -> None:
        before = _read(root, relative_path)
        after = _replace_all(before, pattern, replacement, relative_path)
        if before != after:
            changes.append(Change(root / relative_path, before, after))

    changes.append(
        Change(
            root / "VERSION",
            _read(root, "VERSION"),
            f"{target_version}\n",
        )
    )

    pyproject_version = re.compile(r'(?m)^version = "[^"]*"$')
    for relative_path in PYPROJECT_PATHS:
        plan_once(relative_path, pyproject_version, f'version = "{target_version}"')

    init_version = re.compile(r'(?m)^__version__ = "[^"]*"$')
    for relative_path in INIT_PATHS:
        plan_once(relative_path, init_version, f'__version__ = "{target_version}"')

    package_version = re.compile(r'(?m)^(\s*"version":\s*")[^"]*(")')
    for relative_path in PACKAGE_JSON_PATHS:
        plan_once(relative_path, package_version, rf"\g<1>{target_version}\g<2>")

    plan_all(
        "compose.yaml",
        re.compile(r"(\$\{CG_IMAGE_TAG:-)[^}]+\}"),
        rf"\g<1>{target_version}}}",
    )

    dockerfile_arg = re.compile(r"(?m)^ARG CG_PROJECT_VERSION=.*$")
    for relative_path in DOCKERFILE_PATHS:
        plan_once(relative_path, dockerfile_arg, f"ARG CG_PROJECT_VERSION={target_version}")

    plan_once(
        "README.md",
        re.compile(r"(The locked release candidate is `)[^`]+(`)"),
        rf"\g<1>{target_version}\g<2>",
    )

    changelog = _read(root, "CHANGELOG.md")
    promoted = _changelog_with_release(changelog, target_version, date.today().isoformat())
    changes.append(Change(root / "CHANGELOG.md", changelog, promoted))

    return ReleasePlan(root, current_version, target_version, changes)


def verify_worktree_is_clean(root: Path) -> None:
    status = _run_git(root, "status", "--porcelain")
    if status.strip():
        raise ReleaseError("the worktree must be clean before preparing a release")


def verify_tag_does_not_exist(root: Path, target_version: str) -> None:
    tags = _run_git(root, "tag", "--list", f"v{target_version}")
    if tags.strip():
        raise ReleaseError(f"tag v{target_version} already exists")


def apply_plan(plan: ReleasePlan) -> None:
    for change in plan.changes:
        change.path.write_text(change.after, encoding="utf-8")


def regenerate_openapi(root: Path) -> None:
    script = root / "scripts/export_openapi.py"
    if not script.exists():
        raise ReleaseError(f"OpenAPI export script is missing: {script}")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"OpenAPI snapshot regeneration failed: {detail}")


def allowed_paths(plan: ReleasePlan) -> set[str]:
    return {*plan.rewritten_paths, OPENAPI_PATH}


def verify_only_release_files_changed(root: Path, plan: ReleasePlan) -> None:
    status = _run_git(root, "status", "--porcelain")
    changed: set[str] = set()
    for line in status.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.add(path.strip('"'))
    unexpected = sorted(changed - allowed_paths(plan))
    if unexpected:
        raise ReleaseError(
            "unexpected files changed while preparing the release:\n  " + "\n  ".join(unexpected)
        )


def run_checks(root: Path) -> None:
    result = subprocess.run(["make", "check"], cwd=root, check=False)
    if result.returncode != 0:
        raise ReleaseError("'make check' failed; fix the release before tagging")


def describe(plan: ReleasePlan) -> str:
    lines = [
        f"Release {plan.current_version} -> {plan.target_version}",
        "",
        "Files that would be rewritten:",
        *(f"  {path}" for path in plan.rewritten_paths),
        "",
        "CHANGELOG.md promotes its Unreleased entries under a dated heading.",
    ]
    return "\n".join(lines)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", help="exact version to lock, for example 0.1.0-rc.35")
    parser.add_argument(
        "--bump",
        choices=("rc", "patch", "minor", "major"),
        help="derive the next version from VERSION",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to this checkout)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing")
    parser.add_argument(
        "--skip-openapi",
        action="store_true",
        help="do not regenerate the committed OpenAPI snapshot",
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="do not run 'make check' after rewriting",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    root = arguments.root.resolve()

    try:
        if not (root / "VERSION").exists():
            raise ReleaseError(f"not a repository root: {root}")
        if not arguments.version and not arguments.bump:
            raise ReleaseError("supply --version or --bump")

        if arguments.dry_run:
            if _run_git(root, "status", "--porcelain").strip():
                print(
                    "Warning: the worktree is dirty; the plan reflects the current files.",
                    file=sys.stderr,
                )
        else:
            verify_worktree_is_clean(root)
        current_version = _read(root, "VERSION").strip()
        target_version = arguments.version or next_version(current_version, arguments.bump)
        verify_tag_does_not_exist(root, target_version)
        plan = build_plan(root, target_version)

        if arguments.dry_run:
            print(describe(plan))
            print("\nDry run: no files were written and no checks were run.")
            return 0

        apply_plan(plan)
        if not arguments.skip_openapi:
            print("Regenerating the committed OpenAPI snapshot…")
            regenerate_openapi(root)
        verify_only_release_files_changed(root, plan)
        if not arguments.skip_check:
            print("Running the complete check suite…")
            run_checks(root)
    except ReleaseError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Prepared {target_version} across {len(plan.changes)} files.")
    print("Next:")
    print("  1. Review the diff: git diff (OpenAPI snapshot is regenerated)")
    print(f'  2. Commit: git commit -am "release: prepare {target_version}"')
    print("  3. Push main, then run: make milestone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
