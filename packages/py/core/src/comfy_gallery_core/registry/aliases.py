from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from comfy_gallery_core.db.models import ModelReference, ModelReferenceGroup
from comfy_gallery_core.media.errors import IngestionError

MODEL_FILE_SUFFIX = re.compile(
    r"\.(?:safetensors|ckpt|pt|pth|bin|gguf)$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ReferenceAliasCandidate:
    canonical_key: str
    display_name: str
    reference_type: str
    evidence_method: str
    confidence: float
    conflict_reason: str | None
    references: tuple[ModelReference, ...]


@dataclass(frozen=True, slots=True)
class ReferenceFilterOption:
    reference_id: UUID
    identity_group_id: UUID | None
    reference_type: str
    display_name: str
    occurrence_count: int
    alias_count: int


def model_reference_alias_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip().replace("\\", "/"))
    filename = PurePosixPath(normalized).name
    stem = MODEL_FILE_SUFFIX.sub("", filename)
    return stem.casefold()


def model_reference_alias_display(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip().replace("\\", "/"))
    filename = PurePosixPath(normalized).name
    return MODEL_FILE_SUFFIX.sub("", filename)


async def list_reference_alias_candidates(
    session: AsyncSession,
    *,
    reference_type: str = "lora",
) -> list[ReferenceAliasCandidate]:
    references = list(
        await session.scalars(
            select(ModelReference)
            .options(selectinload(ModelReference.identity_group))
            .where(
                ModelReference.reference_type == reference_type,
                ModelReference.occurrence_count > 0,
            )
            .order_by(ModelReference.raw_value)
        )
    )
    grouped: dict[str, list[ModelReference]] = defaultdict(list)
    for reference in references:
        if reference.identity_group is not None and reference.identity_group.status == "confirmed":
            continue
        grouped[model_reference_alias_key(reference.raw_value)].append(reference)

    candidates: list[ReferenceAliasCandidate] = []
    for canonical_key, aliases in grouped.items():
        if len(aliases) < 2 or len({item.normalized_value for item in aliases}) < 2:
            continue
        artifact_ids = {item.artifact_id for item in aliases if item.artifact_id is not None}
        conflict_reason = (
            "Aliases resolve to different model artifacts." if len(artifact_ids) > 1 else None
        )
        evidence_method = (
            "same_artifact"
            if len(artifact_ids) == 1 and all(item.artifact_id is not None for item in aliases)
            else "basename_stem"
        )
        confidence = 1.0 if evidence_method == "same_artifact" else 0.75
        canonical = _canonical_reference(aliases)
        candidates.append(
            ReferenceAliasCandidate(
                canonical_key=canonical_key,
                display_name=model_reference_alias_display(canonical.raw_value),
                reference_type=reference_type,
                evidence_method=evidence_method,
                confidence=confidence,
                conflict_reason=conflict_reason,
                references=tuple(aliases),
            )
        )
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.conflict_reason is not None,
            -sum(item.occurrence_count for item in candidate.references),
            candidate.display_name.casefold(),
        ),
    )


async def confirm_safe_reference_alias_groups(session: AsyncSession) -> int:
    candidates = await list_reference_alias_candidates(session)
    created_count = 0
    for candidate in candidates:
        if candidate.evidence_method != "same_artifact" or candidate.conflict_reason:
            continue
        group = ModelReferenceGroup(
            reference_type=candidate.reference_type,
            canonical_key=candidate.canonical_key,
            display_name=candidate.display_name,
            source="same_artifact",
            confidence=1.0,
            status="confirmed",
        )
        session.add(group)
        await session.flush()
        for reference in candidate.references:
            reference.identity_group_id = group.id
            reference.identity_group = group
        created_count += 1
    return created_count


async def list_reference_groups(
    session: AsyncSession,
    *,
    reference_type: str | None = None,
    status: str = "confirmed",
) -> list[ModelReferenceGroup]:
    query = (
        select(ModelReferenceGroup)
        .options(selectinload(ModelReferenceGroup.references))
        .where(ModelReferenceGroup.status == status)
    )
    if reference_type is not None:
        query = query.where(ModelReferenceGroup.reference_type == reference_type)
    return list(
        await session.scalars(
            query.order_by(
                ModelReferenceGroup.reference_type,
                ModelReferenceGroup.display_name,
            )
        )
    )


async def confirm_reference_alias_group(
    session: AsyncSession,
    *,
    reference_ids: list[UUID],
    display_name: str | None = None,
) -> ModelReferenceGroup:
    unique_ids = set(reference_ids)
    if len(unique_ids) < 2:
        raise IngestionError(
            code="MODEL_ALIAS_GROUP_TOO_SMALL",
            message="Select at least two workflow references to group.",
        )
    references = list(
        await session.scalars(
            select(ModelReference)
            .options(selectinload(ModelReference.identity_group))
            .where(ModelReference.id.in_(unique_ids))
        )
    )
    if len(references) != len(unique_ids):
        raise IngestionError(
            code="MODEL_ALIAS_REFERENCE_MISSING",
            message="One or more workflow references no longer exist.",
        )
    reference_types = {item.reference_type for item in references}
    if len(reference_types) != 1:
        raise IngestionError(
            code="MODEL_ALIAS_TYPE_MISMATCH",
            message="Checkpoint and LoRA references cannot share an identity group.",
        )
    alias_keys = {model_reference_alias_key(item.raw_value) for item in references}
    if len(alias_keys) != 1:
        raise IngestionError(
            code="MODEL_ALIAS_NAME_MISMATCH",
            message="Selected references do not share the same sanitized basename.",
        )
    artifact_ids = {item.artifact_id for item in references if item.artifact_id is not None}
    if len(artifact_ids) > 1:
        raise IngestionError(
            code="MODEL_ALIAS_ARTIFACT_CONFLICT",
            message="Selected references resolve to different artifacts and cannot be grouped.",
        )
    if any(
        item.identity_group is not None and item.identity_group.status == "confirmed"
        for item in references
    ):
        raise IngestionError(
            code="MODEL_ALIAS_ALREADY_GROUPED",
            message="One or more selected references already belong to a confirmed group.",
        )

    canonical = _canonical_reference(references)
    normalized_display = (display_name or "").strip() or model_reference_alias_display(
        canonical.raw_value
    )
    group = ModelReferenceGroup(
        reference_type=next(iter(reference_types)),
        canonical_key=next(iter(alias_keys)),
        display_name=normalized_display,
        source="manual_alias",
        confidence=1.0,
        status="confirmed",
    )
    session.add(group)
    await session.flush()
    for reference in references:
        reference.identity_group_id = group.id
        reference.identity_group = group
    await session.commit()
    return await _load_group(session, group.id)


async def revoke_reference_alias_group(
    session: AsyncSession,
    *,
    group: ModelReferenceGroup,
) -> ModelReferenceGroup:
    if group.status != "confirmed":
        raise IngestionError(
            code="MODEL_ALIAS_GROUP_NOT_ACTIVE",
            message="Only a confirmed alias group can be undone.",
        )
    group.status = "revoked"
    await session.commit()
    return await _load_group(session, group.id)


async def list_reference_filter_options(
    session: AsyncSession,
    *,
    reference_type: str,
) -> list[ReferenceFilterOption]:
    references = list(
        await session.scalars(
            select(ModelReference)
            .options(selectinload(ModelReference.identity_group))
            .where(
                ModelReference.reference_type == reference_type,
                ModelReference.occurrence_count > 0,
            )
        )
    )
    grouped: dict[UUID, list[ModelReference]] = defaultdict(list)
    confirmed_groups: dict[UUID, ModelReferenceGroup] = {}
    ungrouped: list[ModelReference] = []
    for reference in references:
        group = reference.identity_group
        if group is not None and group.status == "confirmed":
            grouped[group.id].append(reference)
            confirmed_groups[group.id] = group
        else:
            ungrouped.append(reference)

    options = [
        ReferenceFilterOption(
            reference_id=_canonical_reference(aliases).id,
            identity_group_id=group_id,
            reference_type=reference_type,
            display_name=confirmed_groups[group_id].display_name,
            occurrence_count=sum(item.occurrence_count for item in aliases),
            alias_count=len(aliases),
        )
        for group_id, aliases in grouped.items()
    ]
    options.extend(
        ReferenceFilterOption(
            reference_id=reference.id,
            identity_group_id=None,
            reference_type=reference.reference_type,
            display_name=model_reference_alias_display(reference.raw_value),
            occurrence_count=reference.occurrence_count,
            alias_count=1,
        )
        for reference in ungrouped
    )
    return sorted(
        options,
        key=lambda item: (-item.occurrence_count, item.display_name.casefold()),
    )


def reference_identity_ids(reference_id: UUID) -> Select[tuple[UUID]]:
    selected_group_id = (
        select(ModelReference.identity_group_id)
        .where(ModelReference.id == reference_id)
        .scalar_subquery()
    )
    return (
        select(ModelReference.id)
        .outerjoin(
            ModelReferenceGroup,
            ModelReferenceGroup.id == ModelReference.identity_group_id,
        )
        .where(
            or_(
                ModelReference.id == reference_id,
                (
                    (selected_group_id.is_not(None))
                    & (ModelReference.identity_group_id == selected_group_id)
                    & (ModelReferenceGroup.status == "confirmed")
                ),
            )
        )
    )


async def _load_group(
    session: AsyncSession,
    group_id: UUID,
) -> ModelReferenceGroup:
    group = await session.scalar(
        select(ModelReferenceGroup)
        .options(selectinload(ModelReferenceGroup.references))
        .where(ModelReferenceGroup.id == group_id)
    )
    if group is None:
        raise RuntimeError("Model reference group disappeared after persistence.")
    return group


def _canonical_reference(references: list[ModelReference]) -> ModelReference:
    return min(
        references,
        key=lambda item: (
            "/" in item.normalized_value.replace("\\", "/"),
            len(item.normalized_value),
            item.raw_value.casefold(),
            str(item.id),
        ),
    )
