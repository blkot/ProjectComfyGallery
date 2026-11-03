"""Materialize trusted Prompt ID resolution for fast registry lookups."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.db.models import (
    Media,
    MediaAsset,
    MediaPromptIndex,
    WorkflowDisplayProfile,
    WorkflowDisplayRecovery,
    WorkflowSnapshot,
)
from comfy_gallery_core.prompt_registry import parse_prompt_id
from comfy_gallery_core.workflow.display_fields import (
    library_show_nodes,
    saved_fields,
    topology,
    widget_candidates,
    workflow_uuid,
)

ProfilesByScope = dict[str, list[WorkflowDisplayProfile]]


async def sync_media_prompt_index(
    session: AsyncSession,
    *,
    media_id: UUID,
    snapshot: WorkflowSnapshot | None = None,
    asset_sha256: str | None = None,
    profiles_by_scope: ProfilesByScope | None = None,
) -> MediaPromptIndex:
    """Recompute one media's materialized Prompt ID without committing."""

    if snapshot is None:
        snapshot = await session.scalar(
            select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == media_id)
        )
    if asset_sha256 is None:
        asset_sha256 = await session.scalar(
            select(MediaAsset.sha256).where(MediaAsset.media_id == media_id)
        )
    if profiles_by_scope is None:
        profiles_by_scope = await load_profiles_by_scope(session)

    record = await session.get(MediaPromptIndex, media_id)
    if record is None:
        record = MediaPromptIndex(media_id=media_id)
        session.add(record)

    prompt_id: str | None = None
    evidence_source = "none"
    original_sha256: str | None = None
    if snapshot is not None:
        fields = saved_fields(snapshot.raw_metadata or {}, snapshot.api_prompt or {})
        saved = fields.get("prompt_id")
        if saved is not None and isinstance(saved.value, str):
            prompt_id = saved.value
            evidence_source = "save_node"
        else:
            recovered = await session.scalar(
                select(WorkflowDisplayRecovery).where(
                    WorkflowDisplayRecovery.media_id == media_id,
                    WorkflowDisplayRecovery.field_name == "prompt_id",
                )
            )
            if recovered is not None and recovered.original_sha256 == asset_sha256:
                prompt_id = recovered.value
                evidence_source = "verified_history"
                original_sha256 = recovered.original_sha256
            elif snapshot.api_prompt:
                prompt_id = prompt_id_candidate(snapshot, profiles_by_scope)
                if prompt_id is not None:
                    evidence_source = "display_profile"
                else:
                    prompt_id = structural_prompt_id_candidate(snapshot)
                    if prompt_id is not None:
                        evidence_source = "visual_binding"

    parsed = parse_prompt_id(prompt_id)
    record.source_key = parsed.source_key if parsed is not None else None
    record.entry_index = parsed.index if parsed is not None else None
    record.index_key = parsed.index_key if parsed is not None else None
    record.prompt_id = parsed.display if parsed is not None else None
    record.evidence_source = evidence_source
    record.original_sha256 = original_sha256
    return record


async def load_profiles_by_scope(session: AsyncSession) -> ProfilesByScope:
    profiles = list(await session.scalars(select(WorkflowDisplayProfile)))
    profiles_by_scope: ProfilesByScope = {}
    for profile in profiles:
        profiles_by_scope.setdefault(profile.scope, []).append(profile)
    return profiles_by_scope


def prompt_id_candidate(
    snapshot: WorkflowSnapshot,
    profiles_by_scope: ProfilesByScope,
) -> str | None:
    """Return a profile-backed candidate without any database query."""

    workflow_id = workflow_uuid(snapshot.visual_workflow)
    scope = f"workflow:{workflow_id}" if workflow_id else f"media:{snapshot.media_id}"
    profiles = profiles_by_scope.get(scope)
    if not profiles or not snapshot.api_prompt:
        return None
    try:
        signature = topology(snapshot.api_prompt)
        profile = next((item for item in profiles if item.topology_sha256 == signature), None)
        if profile is None:
            return None
        candidates = widget_candidates(
            snapshot.api_prompt,
            profile.bindings,
            snapshot.visual_workflow,
        )
    except ValueError:
        return None
    candidate = candidates.get("prompt_id")
    return candidate[0] if candidate is not None else None


def structural_prompt_id_candidate(snapshot: WorkflowSnapshot) -> str | None:
    """Derive a Prompt ID from library-wired ShowText nodes without a profile.

    The API graph is authoritative for wiring, so a ShowText node linked to a
    XantaPromptLibrary node identifies the prompt-ID display even when the
    workflow has no registered display profile. The value still comes from the
    visual widget snapshot. Ambiguous workflows (two distinct parseable Prompt
    IDs) fail closed instead of guessing.
    """

    api = snapshot.api_prompt or {}
    node_ids = library_show_nodes(api)
    if not node_ids or not snapshot.visual_workflow:
        return None
    values: set[str] = set()
    for node_id in node_ids:
        try:
            candidates = widget_candidates(api, {"prompt_id": node_id}, snapshot.visual_workflow)
        except ValueError:
            continue
        candidate = candidates.get("prompt_id")
        text = candidate[0] if candidate is not None else None
        if not isinstance(text, str):
            continue
        parsed = parse_prompt_id(text)
        if parsed is not None:
            values.add(parsed.display)
    return values.pop() if len(values) == 1 else None


async def rebuild_prompt_index(
    session: AsyncSession,
    *,
    batch_size: int = 256,
) -> int:
    """Backfill one materialized index row for every media record."""

    media_ids = list(await session.scalars(select(Media.id).order_by(Media.id)))
    profiles_by_scope = await load_profiles_by_scope(session)
    processed = 0
    for offset in range(0, len(media_ids), batch_size):
        batch_ids = media_ids[offset : offset + batch_size]
        rows = list(
            (
                await session.execute(
                    select(Media.id, MediaAsset.sha256, WorkflowSnapshot)
                    .outerjoin(MediaAsset, MediaAsset.media_id == Media.id)
                    .outerjoin(WorkflowSnapshot, WorkflowSnapshot.media_id == Media.id)
                    .where(Media.id.in_(batch_ids))
                )
            ).all()
        )
        for media_id, asset_sha256, snapshot in rows:
            await sync_media_prompt_index(
                session,
                media_id=media_id,
                snapshot=snapshot,
                asset_sha256=asset_sha256,
                profiles_by_scope=profiles_by_scope,
            )
            processed += 1
        await session.commit()
    return processed
