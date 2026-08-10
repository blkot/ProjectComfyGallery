from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_api.dependencies import (
    CsrfPrincipalDep,
    DbSessionDep,
    PrincipalDep,
    SettingsDep,
)
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import JobResponse
from comfy_gallery_api.spatial_conversion_schemas import (
    SpatialConversionCreateRequest,
    SpatialConversionResponse,
    SpatialConversionStateResponse,
)
from comfy_gallery_core.db.models import Job, Media, MediaVariant, SpatialConversionRun
from comfy_gallery_core.queue import (
    enqueue_spatial_conversion,
    enqueue_spatial_publish_retry,
    enqueue_spatial_reconciliation,
)

router = APIRouter(tags=["spatial conversion"])
ACTIVE_STATUSES = ("queued", "submitting", "processing")
CONVERTIBLE_MEDIA_STATUSES = ("ready", "ready_with_warnings")


@router.get(
    "/api/v1/media/{media_id}/spatial-conversions/current",
    response_model=SpatialConversionStateResponse,
)
async def get_current_spatial_conversion(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SpatialConversionStateResponse:
    await _require_video(session, media_id)
    conversion = await session.scalar(
        select(SpatialConversionRun)
        .where(SpatialConversionRun.media_id == media_id)
        .order_by(SpatialConversionRun.created_at.desc())
        .limit(1)
    )
    job = await _job_for_run(session, conversion.id) if conversion else None
    return _state(settings.mss_base_url is not None, conversion, job)


@router.get(
    "/api/v1/spatial-conversions/{run_id}",
    response_model=SpatialConversionStateResponse,
)
async def get_spatial_conversion(
    run_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SpatialConversionStateResponse:
    conversion = await session.get(SpatialConversionRun, run_id)
    if conversion is None:
        raise ApiError(
            status_code=404,
            code="SPATIAL_CONVERSION_NOT_FOUND",
            message="The spatial conversion request was not found.",
        )
    return _state(
        settings.mss_base_url is not None,
        conversion,
        await _job_for_run(session, conversion.id),
    )


@router.post(
    "/api/v1/spatial-conversions/{run_id}/refresh",
    response_model=SpatialConversionStateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_spatial_conversion(
    run_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SpatialConversionStateResponse:
    conversion = await session.get(SpatialConversionRun, run_id)
    if conversion is None:
        raise ApiError(
            status_code=404,
            code="SPATIAL_CONVERSION_NOT_FOUND",
            message="The spatial conversion request was not found.",
        )
    # A completion event can win after the page rendered an active run but before
    # this command arrives. Return that terminal projection idempotently so the
    # browser can observe the authoritative outcome instead of receiving a 409.
    if conversion.status not in ACTIVE_STATUSES:
        return _state(
            settings.mss_base_url is not None,
            conversion,
            await _job_for_run(session, conversion.id),
        )
    if not conversion.mss_batch_id:
        raise ApiError(
            status_code=409,
            code="SPATIAL_CONVERSION_NOT_REFRESHABLE",
            message="This conversion has no active MSS batch to refresh.",
        )
    # Claim is made by the actor. Setting this due makes refresh an actual
    # one-shot request rather than a message that the throttle immediately drops.
    conversion.next_reconciliation_at = datetime.now(UTC)
    await session.commit()
    enqueue_spatial_reconciliation(run_id=str(run_id))
    return _state(
        settings.mss_base_url is not None, conversion, await _job_for_run(session, conversion.id)
    )


@router.post(
    "/api/v1/spatial-conversions/{run_id}/retry-publish",
    response_model=SpatialConversionStateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_spatial_conversion_publish(
    run_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SpatialConversionStateResponse:
    conversion = await session.get(SpatialConversionRun, run_id)
    if conversion is None:
        raise ApiError(
            status_code=404,
            code="SPATIAL_CONVERSION_NOT_FOUND",
            message="The spatial conversion request was not found.",
        )
    if not conversion.mss_batch_id or conversion.publish_status not in {"failed", "skipped"}:
        raise ApiError(
            status_code=409,
            code="SPATIAL_PUBLISH_NOT_RETRYABLE",
            message="Only a failed or skipped MSS publication can be retried.",
        )
    enqueue_spatial_publish_retry(run_id=str(run_id))
    return _state(
        settings.mss_base_url is not None, conversion, await _job_for_run(session, conversion.id)
    )


@router.post(
    "/api/v1/media/{media_id}/spatial-conversions",
    response_model=SpatialConversionStateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_spatial_conversion(
    media_id: UUID,
    request: SpatialConversionCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SpatialConversionStateResponse:
    media = await _require_video(session, media_id)
    if media.status not in CONVERTIBLE_MEDIA_STATUSES:
        raise ApiError(
            status_code=409,
            code="MEDIA_NOT_READY",
            message="Only ready videos can be sent for spatial conversion.",
        )
    if settings.mss_base_url is None:
        raise ApiError(
            status_code=503,
            code="MSS_NOT_CONFIGURED",
            message="The spatial conversion service is not configured.",
        )

    active = await _active_run(session, media_id)
    if active is not None:
        return _state(True, active, await _job_for_run(session, active.id))

    options = {key: value for key, value in request.model_dump().items() if value is not None}
    previous_variant_id = await session.scalar(
        select(MediaVariant.id).where(
            MediaVariant.media_id == media_id,
            MediaVariant.role == "spatial_video",
            MediaVariant.status == "ready",
            MediaVariant.is_active.is_(True),
        )
    )
    conversion = SpatialConversionRun(
        media_id=media_id,
        created_by_user_id=principal.user.id,
        requested_options=options,
        previous_variant_id=previous_variant_id,
    )
    session.add(conversion)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        active = await _active_run(session, media_id)
        if active is None:
            raise
        return _state(True, active, await _job_for_run(session, active.id))

    job = Job(
        kind="spatial_conversion",
        queue="spatial",
        resource_type="spatial_conversion_run",
        resource_id=conversion.id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    try:
        enqueue_spatial_conversion(run_id=str(conversion.id), job_id=str(job.id))
    except Exception as exc:
        now = datetime.now(UTC)
        conversion.status = "failed"
        conversion.error_code = "QUEUE_UNAVAILABLE"
        conversion.error_message = "The spatial conversion could not be queued."
        conversion.completed_at = now
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = conversion.error_message
        job.error_details = {"retryable": True}
        job.completed_at = now
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The spatial conversion could not be queued.",
        ) from exc
    await session.refresh(conversion)
    await session.refresh(job)
    return _state(True, conversion, job)


async def _require_video(session: AsyncSession, media_id: UUID) -> Media:
    media = await session.get(Media, media_id)
    if media is None:
        raise ApiError(status_code=404, code="MEDIA_NOT_FOUND", message="The media was not found.")
    if media.kind != "video":
        raise ApiError(
            status_code=409,
            code="MEDIA_NOT_VIDEO",
            message="Only video media can have a spatial conversion.",
        )
    return media


async def _active_run(
    session: AsyncSession,
    media_id: UUID,
) -> SpatialConversionRun | None:
    return cast(
        SpatialConversionRun | None,
        await session.scalar(
            select(SpatialConversionRun)
            .where(
                SpatialConversionRun.media_id == media_id,
                SpatialConversionRun.status.in_(ACTIVE_STATUSES),
            )
            .order_by(SpatialConversionRun.created_at.desc())
            .limit(1)
        ),
    )


async def _job_for_run(session: AsyncSession, run_id: UUID) -> Job | None:
    return cast(
        Job | None,
        await session.scalar(
            select(Job)
            .where(
                Job.kind == "spatial_conversion",
                Job.resource_id == run_id,
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        ),
    )


def _state(
    configured: bool,
    conversion: SpatialConversionRun | None,
    job: Job | None,
) -> SpatialConversionStateResponse:
    return SpatialConversionStateResponse(
        configured=configured,
        conversion=(
            SpatialConversionResponse.model_validate(conversion) if conversion is not None else None
        ),
        job=JobResponse.model_validate(job) if job is not None else None,
    )
