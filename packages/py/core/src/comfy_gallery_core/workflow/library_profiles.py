"""Apply a pinned display profile to Gallery snapshots without any ComfyUI connection."""

from __future__ import annotations

import asyncio
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.db import get_database
from comfy_gallery_core.db.models import WorkflowDisplayProfile, WorkflowSnapshot
from comfy_gallery_core.workflow.display_fields import (
    WidgetCandidateSource,
    topology,
    widget_candidates,
    workflow_uuid,
)


def _scope(media_id: UUID, visual: dict[str, object] | None) -> str:
    uid = workflow_uuid(visual)
    return f"workflow:{uid}" if uid else f"media:{media_id}"


async def candidate_fields(
    session: AsyncSession,
    snapshot: WorkflowSnapshot,
    *,
    profiles: Sequence[WorkflowDisplayProfile] | None = None,
) -> dict[str, tuple[str, str, WidgetCandidateSource]]:
    if not snapshot.api_prompt:
        return {}
    if profiles is None:
        profiles = list(
            await session.scalars(
                select(WorkflowDisplayProfile).where(
                    WorkflowDisplayProfile.scope
                    == _scope(snapshot.media_id, snapshot.visual_workflow)
                )
            )
        )
    else:
        profiles = [
            profile
            for profile in profiles
            if profile.scope == _scope(snapshot.media_id, snapshot.visual_workflow)
        ]
    if not profiles:
        return {}
    try:
        signature = topology(snapshot.api_prompt)
        profile = next((p for p in profiles if p.topology_sha256 == signature), None)
        if profile is None:
            return {}
        values = widget_candidates(
            snapshot.api_prompt,
            profile.bindings,
            snapshot.visual_workflow,
        )
    except ValueError:
        return {}
    return {
        field: (value, profile.bindings[field], source)
        for field, (value, source) in values.items()
        if value is not None
    }


async def install_profile(
    session: AsyncSession, spec: dict[str, object], *, apply: bool
) -> dict[str, object]:
    reference_id = UUID(str(spec.get("reference_media")))
    reference = (
        await session.execute(
            select(WorkflowSnapshot.api_prompt, WorkflowSnapshot.visual_workflow).where(
                WorkflowSnapshot.media_id == reference_id
            )
        )
    ).one_or_none()
    if not reference or not reference.api_prompt:
        raise ValueError("Reference media has no embedded API graph.")
    bindings = spec.get("bindings")
    if (
        not isinstance(bindings, dict)
        or not bindings
        or not all(isinstance(k, str) and isinstance(v, str) for k, v in bindings.items())
    ):
        raise ValueError("Missing or invalid field bindings.")
    uid = workflow_uuid(reference.visual_workflow)
    signature = topology(reference.api_prompt)
    if (
        type(spec.get("version")) is not int
        or spec["version"] != 1
        or (spec.get("workflow_uuid") != uid or spec.get("topology_sha256") != signature)
    ):
        raise ValueError("Profile no longer matches its reference snapshot.")
    widget_candidates(reference.api_prompt, bindings, reference.visual_workflow)
    scope = _scope(reference_id, reference.visual_workflow)
    existing = await session.get(WorkflowDisplayProfile, (scope, signature))
    if existing is not None and existing.bindings != bindings:
        raise ValueError("A different mapping already exists for this graph; no changes made.")

    query = select(WorkflowSnapshot.api_prompt, WorkflowSnapshot.visual_workflow).where(
        WorkflowSnapshot.visual_workflow["id"].as_string() == uid
        if uid
        else WorkflowSnapshot.media_id == reference_id
    )
    graphs = await session.stream(query.execution_options(yield_per=32))
    counts: Counter[str] = Counter()
    matched = examined = 0
    async for row in graphs:
        examined += 1
        api, visual = row
        if not api:
            continue
        try:
            if topology(api) != signature:
                continue
            values = widget_candidates(api, bindings, visual)
        except ValueError:
            continue
        matched += 1
        counts.update(k for k, (value, _source) in values.items() if value is not None)
    if apply and existing is None:
        session.add(
            WorkflowDisplayProfile(
                scope=scope,
                topology_sha256=signature,
                reference_media_id=reference_id,
                bindings=bindings,
            )
        )
        await session.commit()
    return {
        "workflow_uuid": uid,
        "examined": examined,
        "matched": matched,
        "candidate_counts": dict(counts),
        "applied": apply,
    }


async def migrate_display(path: Path, *, apply: bool) -> None:
    spec = json.loads(await asyncio.to_thread(path.read_text))
    if not isinstance(spec, dict):
        raise ValueError("Expected a versioned profile object.")
    db = get_database()
    try:
        async with db.session() as session:
            print(json.dumps(await install_profile(session, spec, apply=apply)))
    finally:
        await db.dispose()
