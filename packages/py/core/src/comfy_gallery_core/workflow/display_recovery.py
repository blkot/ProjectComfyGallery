"""Explicit, file-scoped recovery from a retained ComfyUI execution or its private archive."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select

from comfy_gallery_core.config import get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.db.models import MediaAsset, WorkflowDisplayRecovery, WorkflowSnapshot
from comfy_gallery_core.workflow.display_fields import (
    read_shows,
    topology,
    widget_candidates,
    workflow_uuid,
)

MAX_HISTORY = 16 * 1024 * 1024


@dataclass(frozen=True)
class Target:
    media_id: UUID
    filename: str
    sha256: str
    size: int
    api: dict[str, object]
    workflow_id: str | None


def ensure_scope(reference: Target, target: Target) -> str:
    if reference.media_id != target.media_id and (
        not reference.workflow_id or reference.workflow_id != target.workflow_id
    ):
        raise ValueError("Different or absent workflow UUID; do not reuse this profile.")
    signature = topology(reference.api)
    if signature != topology(target.api):
        raise ValueError("Workflow wiring or regex settings changed; review a new profile.")
    return signature


def profile_for(reference: Target, bindings: Mapping[str, str]) -> dict[str, object]:
    return {
        "version": 1,
        "reference_media": str(reference.media_id),
        "workflow_uuid": reference.workflow_id,
        "topology_sha256": topology(reference.api),
        "bindings": dict(bindings),
    }


def profile_hash(profile: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _read_profile(path: Path) -> dict[str, object]:
    p = json.loads(path.read_text())
    if (
        not isinstance(p, dict)
        or type(p.get("version")) is not int
        or p["version"] != 1
        or not isinstance(p.get("bindings"), dict)
    ):
        raise ValueError("Invalid recovery profile.")
    return p


def _write_profile(path: Path, profile: dict[str, object]) -> None:
    with path.open("x") as stream:
        json.dump(profile, stream, indent=2)


def checked_job(payload: bytes, job_id: UUID, target: Target) -> dict[str, object]:
    tree = json.loads(payload)
    job = tree.get(str(job_id)) if isinstance(tree, dict) else None
    if not isinstance(job, dict) or job.get("status", {}).get("status_str") != "success":
        raise ValueError("No successful retained execution for this job ID.")
    p = job.get("prompt")
    if not isinstance(p, list) or len(p) < 4 or p[1] != str(job_id) or not isinstance(p[2], dict):
        raise ValueError("History is missing its executed API graph.")
    if topology(p[2]) != topology(target.api):
        raise ValueError("History graph differs from the embedded API graph.")
    if target.workflow_id:
        extra = p[3].get("extra_pnginfo", {}) if isinstance(p[3], dict) else {}
        if workflow_uuid(extra.get("workflow")) != target.workflow_id:
            raise ValueError("History workflow UUID differs from the embedded workflow.")
    outputs = job.get("outputs")
    if not isinstance(outputs, dict):
        raise ValueError("No execution outputs available.")
    return outputs


def locators(outputs: Mapping[str, object], target: Target) -> list[dict[str, str]]:
    matches = []
    for node_id, out in outputs.items():
        node = target.api.get(node_id)
        if not isinstance(node, dict) or node.get("class_type") != "XantaSaveAndUpload":
            continue
        images = out.get("images") if isinstance(out, dict) else None
        if not isinstance(images, list):
            continue
        for image in images:
            if not isinstance(image, dict) or image.get("type") != "output":
                continue
            name = image.get("filename")
            sub = image.get("subfolder", "")
            if name != target.filename or not isinstance(sub, str):
                continue
            if (
                any(v in name for v in ("/", "\\", ":", "\x00"))
                or any(v in sub for v in ("\\", ":", "\x00"))
                or sub.startswith("/")
                or ".." in sub.split("/")
            ):
                continue
            matches.append({"filename": name, "subfolder": sub, "type": "output"})
    return matches


def capture_archive(
    path: Path, target: Target, job_id: UUID, base_url: str, user: str | None = None
) -> None:
    if path.exists():
        raise ValueError("Archive already exists; refusing to replace it.")
    headers = {"Comfy-User": user} if user else {}
    with httpx.Client(
        base_url=base_url.rstrip("/") + "/",
        headers=headers,
        timeout=20,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        payload = bytearray()
        with client.stream("GET", f"history/{job_id}") as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                if len(payload) + len(chunk) > MAX_HISTORY:
                    raise ValueError("History exceeds the recovery size limit.")
                payload.extend(chunk)
        outputs = checked_job(bytes(payload), job_id, target)
        for loc in locators(outputs, target):
            with tempfile.TemporaryFile() as file:
                digest = hashlib.sha256()
                with client.stream("GET", "view", params=loc) as response:
                    if response.status_code == 404:
                        continue
                    response.raise_for_status()
                    for chunk in response.iter_bytes():
                        if file.tell() + len(chunk) > target.size:
                            break
                        file.write(chunk)
                        digest.update(chunk)
                    else:
                        if file.tell() == target.size and digest.hexdigest() == target.sha256:
                            file.seek(0)

                            # The archive is operator-owned private evidence, never an upload API.
                            with (
                                os.fdopen(
                                    os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
                                ) as output,
                                zipfile.ZipFile(output, "w") as archive,
                            ):
                                archive.writestr("history.json", bytes(payload))
                                archive.writestr("locator.json", json.dumps(loc))
                                with archive.open("output.png", "w") as entry:
                                    shutil.copyfileobj(file, entry)
                            return
    raise ValueError("No job output matched this media's original SHA-256 and filename.")


def verified_values(
    path: Path, *, reference: Target, target: Target, job_id: UUID, bindings: Mapping[str, str]
) -> tuple[str, dict[str, str]]:
    signature = ensure_scope(reference, target)
    with zipfile.ZipFile(path) as archive:
        if (
            archive.getinfo("history.json").file_size > MAX_HISTORY
            or archive.getinfo("locator.json").file_size > 8192
        ):
            raise ValueError("Oversized evidence archive.")
        outputs = checked_job(archive.read("history.json"), job_id, target)
        if json.loads(archive.read("locator.json")) not in locators(outputs, target):
            raise ValueError("Archived locator does not belong to this execution output.")
        if archive.getinfo("output.png").file_size != target.size:
            raise ValueError("Output size differs from the gallery original.")
        with archive.open("output.png") as output:
            digest = hashlib.sha256()
            for chunk in iter(lambda: output.read(1024 * 1024), b""):
                digest.update(chunk)
            if digest.hexdigest() != target.sha256:
                raise ValueError("Output SHA-256 differs from the gallery original.")
    return signature, read_shows(target.api, outputs, bindings)


async def recover(args: argparse.Namespace) -> None:
    settings = get_settings()
    db = get_database()
    bindings = {}
    supplied_profile = None
    reference_id = args.reference_media
    if args.profile:
        if reference_id or args.bind:
            raise ValueError("Use either a saved profile or explicit reference/bindings.")
        supplied_profile = _read_profile(args.profile)
        reference_id = UUID(str(supplied_profile.get("reference_media")))
        records = supplied_profile["bindings"]
        if not isinstance(records, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in records.items()
        ):
            raise ValueError("Invalid profile bindings.")
        bindings.update(records)
    for assignment in args.bind or []:
        field, sep, node = assignment.partition("=")
        if not sep or not node or field in bindings:
            raise ValueError("Bindings must be unique FIELD=SHOW_NODE_ID pairs.")
        bindings[field] = node
    if not reference_id or not bindings:
        raise ValueError("Supply a profile or a reference media and at least one binding.")
    try:
        async with db.session() as session:

            async def load(media_id: UUID) -> Target:
                row = (
                    await session.execute(
                        select(MediaAsset, WorkflowSnapshot)
                        .join(WorkflowSnapshot, WorkflowSnapshot.media_id == MediaAsset.media_id)
                        .where(MediaAsset.media_id == media_id)
                    )
                ).one_or_none()
                if row is None or not row[1].api_prompt:
                    raise ValueError(f"No embedded API graph for {media_id}.")
                asset, snapshot = row
                return Target(
                    media_id,
                    asset.original_filename,
                    asset.sha256,
                    asset.byte_size,
                    snapshot.api_prompt,
                    workflow_uuid(snapshot.visual_workflow),
                )

            target, reference = await load(args.media), await load(reference_id)
            profile = profile_for(reference, bindings)
            if supplied_profile is not None and supplied_profile != profile:
                raise ValueError("Saved profile no longer matches its reference workflow.")
            ensure_scope(reference, target)
            if args.job is None:
                if args.apply or args.archive_out or args.offline:
                    raise ValueError("A job ID is required to verify or apply historical values.")
                candidates = widget_candidates(target.api, bindings)
                if args.profile_out:
                    _write_profile(args.profile_out, profile)
                print(
                    json.dumps(
                        {
                            "media": str(args.media),
                            "source": "unverified_widget",
                            "candidates": candidates,
                            "applied": False,
                        },
                        ensure_ascii=False,
                    )
                )
                return
            with tempfile.TemporaryDirectory() as tmp:
                archive = args.offline or args.archive_out or Path(tmp) / "verified.zip"
                if not args.offline:
                    if not settings.comfyui_base_url:
                        raise ValueError("No configured ComfyUI URL.")
                    await asyncio.to_thread(
                        capture_archive,
                        archive,
                        target,
                        args.job,
                        settings.comfyui_base_url,
                        settings.comfyui_user,
                    )
                signature, values = verified_values(
                    archive, reference=reference, target=target, job_id=args.job, bindings=bindings
                )
            if args.profile_out:
                _write_profile(args.profile_out, profile)
            if args.apply:
                for name, value in values.items():
                    record = await session.get(WorkflowDisplayRecovery, (args.media, name))
                    attrs = dict(
                        value=value,
                        original_sha256=target.sha256,
                        profile_sha256=profile_hash(profile),
                        workflow_uuid=target.workflow_id,
                        node_id=bindings[name],
                        job_id=args.job,
                    )
                    if record is not None:
                        if any(getattr(record, k) != v for k, v in attrs.items()):
                            raise ValueError(
                                f"Conflicting recovery for {name}; existing value retained."
                            )
                    else:
                        session.add(
                            WorkflowDisplayRecovery(media_id=args.media, field_name=name, **attrs)
                        )
                await session.commit()
            print(
                json.dumps(
                    {
                        "media": str(args.media),
                        "workflow_uuid": target.workflow_id,
                        "topology_sha256": signature,
                        "fields": values,
                        "applied": args.apply,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        await db.dispose()


def register_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    cmd = subparsers.add_parser(
        "recover-display", help="Preview or apply verified historical display fields"
    )
    cmd.add_argument("--reference-media", type=UUID)
    cmd.add_argument("--profile", type=Path, help="Saved versioned reference and bindings")
    cmd.add_argument("--profile-out", type=Path, help="Write the verified profile for reuse")
    cmd.add_argument("--media", type=UUID, required=True)
    cmd.add_argument(
        "--job", type=UUID, help="Without a job, only preview unverified cached widget text"
    )
    cmd.add_argument("--bind", action="append", metavar="FIELD=SHOW_NODE_ID")
    group = cmd.add_mutually_exclusive_group()
    group.add_argument("--archive-out", type=Path)
    group.add_argument("--offline", type=Path)
    cmd.add_argument("--apply", action="store_true")
