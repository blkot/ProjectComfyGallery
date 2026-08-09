from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from comfy_gallery_api.dependencies import (
    CsrfPrincipalDep,
    DbSessionDep,
    PrincipalDep,
    SettingsDep,
)
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import JobResponse
from comfy_gallery_api.workflow_input_schemas import (
    WorkflowInputAssetResponse,
    WorkflowInputListResponse,
    WorkflowInputReferenceResponse,
    WorkflowInputResolveAcceptedResponse,
)
from comfy_gallery_core.db.models import (
    Media,
    WorkflowInputAsset,
    WorkflowInputReference,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path
from comfy_gallery_core.queue import enqueue_workflow_input_capture
from comfy_gallery_core.workflow.input_media import create_capture_job_if_needed

router = APIRouter(prefix="/api/v1/media", tags=["workflow inputs"])


@router.get(
    "/{media_id}/workflow-inputs",
    response_model=WorkflowInputListResponse,
)
async def list_workflow_inputs(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> WorkflowInputListResponse:
    if await session.get(Media, media_id) is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    snapshot_id = await session.scalar(
        select(WorkflowSnapshot.id).where(WorkflowSnapshot.media_id == media_id)
    )
    references = (
        list(
            await session.scalars(
                select(WorkflowInputReference)
                .options(selectinload(WorkflowInputReference.asset))
                .where(WorkflowInputReference.snapshot_id == snapshot_id)
                .order_by(
                    WorkflowInputReference.created_at,
                    WorkflowInputReference.id,
                )
            )
        )
        if snapshot_id is not None
        else []
    )
    items = [_reference_response(media_id, reference) for reference in references]
    ready_count = sum(item.status == "ready" for item in items)
    return WorkflowInputListResponse(
        media_id=media_id,
        items=items,
        total=len(items),
        ready_count=ready_count,
        unresolved_count=len(items) - ready_count,
    )


@router.get(
    "/{media_id}/workflow-inputs/{input_id}/content",
    response_class=FileResponse,
)
async def get_workflow_input_content(
    media_id: UUID,
    input_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    reference = await _load_reference(session, media_id=media_id, input_id=input_id)
    asset = reference.asset
    if reference.status != "ready" or asset is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INPUT_NOT_AVAILABLE",
            message="The workflow input has not been captured into managed storage.",
        )
    try:
        path = safe_managed_path(settings, asset.managed_path)
    except IngestionError as error:
        raise ApiError(
            status_code=500,
            code=error.code,
            message=error.message,
            details=error.details,
        ) from error
    if not path.is_file():
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INPUT_FILE_MISSING",
            message="The captured workflow input is missing from managed storage.",
        )
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=None,
        content_disposition_type="inline",
    )


@router.post(
    "/{media_id}/workflow-inputs/resolve",
    response_model=WorkflowInputResolveAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def resolve_workflow_inputs(
    media_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> WorkflowInputResolveAcceptedResponse:
    if await session.get(Media, media_id) is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    if settings.comfyui_base_url is None:
        raise ApiError(
            status_code=409,
            code="COMFYUI_NOT_CONFIGURED",
            message="Configure CG_COMFYUI_BASE_URL before resolving workflow inputs.",
        )
    reservation = await create_capture_job_if_needed(
        session,
        media_id=media_id,
        settings=settings,
    )
    job = reservation.job
    if job is None:
        raise ApiError(
            status_code=409,
            code="WORKFLOW_INPUTS_NOT_PENDING",
            message="This media has no unresolved workflow inputs to capture.",
        )
    if reservation.created:
        try:
            enqueue_workflow_input_capture(media_id=str(media_id), job_id=str(job.id))
        except Exception as exc:
            job.status = "failed"
            job.error_code = "QUEUE_UNAVAILABLE"
            job.error_message = "Workflow input capture could not be queued."
            job.error_details = {"retryable": True}
            job.completed_at = datetime.now(UTC)
            await session.commit()
            raise ApiError(
                status_code=503,
                code="QUEUE_UNAVAILABLE",
                message="Workflow input capture could not be queued.",
            ) from exc
    return WorkflowInputResolveAcceptedResponse(
        media_id=media_id,
        job=JobResponse.model_validate(job),
    )


async def _load_reference(
    session: DbSessionDep,
    *,
    media_id: UUID,
    input_id: UUID,
) -> WorkflowInputReference:
    reference = await session.scalar(
        select(WorkflowInputReference)
        .join(WorkflowSnapshot, WorkflowInputReference.snapshot_id == WorkflowSnapshot.id)
        .options(selectinload(WorkflowInputReference.asset))
        .where(
            WorkflowInputReference.id == input_id,
            WorkflowSnapshot.media_id == media_id,
        )
    )
    if reference is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_INPUT_NOT_FOUND",
            message="The workflow input reference was not found for this media.",
        )
    return reference


def _reference_response(
    media_id: UUID,
    reference: WorkflowInputReference,
) -> WorkflowInputReferenceResponse:
    asset: WorkflowInputAsset | None = reference.asset
    asset_response = (
        WorkflowInputAssetResponse(
            id=asset.id,
            sha256=asset.sha256,
            kind=asset.kind,
            detected_format=asset.detected_format,
            mime_type=asset.mime_type,
            byte_size=asset.byte_size,
            width=asset.width,
            height=asset.height,
            duration_seconds=asset.duration_seconds,
            frame_rate=asset.frame_rate,
            container=asset.container,
            video_codec=asset.video_codec,
            audio_codec=asset.audio_codec,
        )
        if asset is not None
        else None
    )
    return WorkflowInputReferenceResponse(
        id=reference.id,
        status=reference.status,
        representation=reference.representation,
        original_node_id=reference.original_node_id,
        class_type=reference.class_type,
        locator=reference.locator,
        input_name=reference.input_name,
        media_kind_hint=reference.media_kind_hint,
        source_filename=reference.source_filename,
        source_subfolder=reference.source_subfolder,
        source_type=reference.source_type,
        raw_value=reference.raw_value,
        attempt_count=reference.attempt_count,
        last_attempt_at=reference.last_attempt_at,
        resolved_at=reference.resolved_at,
        last_error_code=reference.last_error_code,
        last_error_message=reference.last_error_message,
        resolution_details=reference.resolution_details,
        asset=asset_response,
        content_url=(
            f"/api/v1/media/{media_id}/workflow-inputs/{reference.id}/content"
            if reference.status == "ready" and asset is not None
            else None
        ),
    )
