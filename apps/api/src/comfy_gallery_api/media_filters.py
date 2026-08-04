from __future__ import annotations

from sqlalchemy import String, and_, cast, or_, select
from sqlalchemy.sql import ColumnElement

from comfy_gallery_core.db.models import (
    ExtractionRun,
    Media,
    ModelArtifact,
    ModelReference,
    ModelReferenceGroup,
    ModelUsage,
    SemanticObservation,
    WorkflowSnapshot,
)

MEDIA_SEARCH_QUERY_MAX_LENGTH = 256
SUCCESSFUL_EXTRACTION_STATUSES = ("succeeded", "completed_with_warnings")


def normalize_media_search_query(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def media_keyword_filter(query: str | None) -> ColumnElement[bool] | None:
    normalized_query = normalize_media_search_query(query)
    if normalized_query is None:
        return None
    pattern = f"%{_escape_like(normalized_query)}%"

    model_match = (
        select(ModelUsage.id)
        .join(WorkflowSnapshot, WorkflowSnapshot.id == ModelUsage.snapshot_id)
        .join(ModelReference, ModelReference.id == ModelUsage.model_reference_id)
        .outerjoin(
            ModelReferenceGroup,
            ModelReferenceGroup.id == ModelReference.identity_group_id,
        )
        .outerjoin(ModelArtifact, ModelArtifact.id == ModelUsage.artifact_id)
        .where(
            WorkflowSnapshot.media_id == Media.id,
            ModelUsage.observation_type.in_(("checkpoint_reference", "lora_reference")),
            or_(
                ModelReference.raw_value.ilike(pattern, escape="\\"),
                ModelReference.normalized_value.ilike(pattern, escape="\\"),
                and_(
                    ModelReferenceGroup.status == "confirmed",
                    ModelReferenceGroup.display_name.ilike(pattern, escape="\\"),
                ),
                and_(
                    ModelReference.resolution_state == "resolved",
                    or_(
                        ModelArtifact.display_name.ilike(pattern, escape="\\"),
                        ModelArtifact.file_name.ilike(pattern, escape="\\"),
                    ),
                ),
            ),
        )
        .exists()
    )
    prompt_match = (
        select(SemanticObservation.id)
        .join(ExtractionRun, ExtractionRun.id == SemanticObservation.run_id)
        .join(WorkflowSnapshot, WorkflowSnapshot.id == ExtractionRun.snapshot_id)
        .where(
            WorkflowSnapshot.media_id == Media.id,
            ExtractionRun.is_current.is_(True),
            ExtractionRun.status.in_(SUCCESSFUL_EXTRACTION_STATUSES),
            SemanticObservation.observation_type == "prompt",
            SemanticObservation.role.in_(("positive", "negative")),
            cast(SemanticObservation.value, String).ilike(pattern, escape="\\"),
        )
        .exists()
    )
    return or_(model_match, prompt_match)


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
