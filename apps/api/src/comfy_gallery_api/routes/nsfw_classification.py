from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select
from uuid6 import uuid7

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import JobResponse
from comfy_gallery_api.nsfw_schemas import (
    MediaSafetyAssessmentResponse,
    MediaSafetyClassificationBatchResponse,
    MediaSafetyClassificationRequest,
    MediaSafetyClassificationStatusResponse,
)
from comfy_gallery_api.routes.evaluations import _resolve_membership_media_ids
from comfy_gallery_core.db.models import Job, Media, MediaSafetyAssessment
from comfy_gallery_core.nsfw import assessment_matches_settings
from comfy_gallery_core.queue import enqueue_nsfw_classification

router = APIRouter(prefix="/api/v1/media", tags=["media safety"])
CLASSIFICATION_JOB_KIND = "classify_media_nsfw"
ACTIVE_JOB_STATUSES = ("queued", "running")
CLASSIFIABLE_MEDIA_STATUSES = ("ready", "ready_with_warnings")


@router.post(
    "/bulk/nsfw-classification",
    response_model=MediaSafetyClassificationBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_media_safety_classification(
    request: MediaSafetyClassificationRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> MediaSafetyClassificationBatchResponse:
    _require_classifier_enabled(settings.nsfw_classifier_enabled)
    media_ids = await _resolve_membership_media_ids(session, request)
    if len(media_ids) > settings.nsfw_max_images_per_request:
        raise ApiError(
            status_code=422,
            code="NSFW_CLASSIFICATION_BATCH_TOO_LARGE",
            message=(
                "The selected scope exceeds the per-request image limit of "
                f"{settings.nsfw_max_images_per_request:,}."
            ),
        )
    if not media_ids:
        return MediaSafetyClassificationBatchResponse(
            requested_count=0,
            queued_count=0,
            reused_count=0,
            skipped_count=0,
            queue_failed_count=0,
        )

    records = list(
        await session.scalars(
            select(Media).where(Media.id.in_(media_ids)).order_by(Media.id).with_for_update()
        )
    )
    by_id = {record.id: record for record in records}
    active_jobs = list(
        await session.scalars(
            select(Job)
            .where(
                Job.kind == CLASSIFICATION_JOB_KIND,
                Job.resource_type == "media",
                Job.resource_id.in_(media_ids),
                Job.status.in_(ACTIVE_JOB_STATUSES),
            )
            .order_by(Job.created_at.desc())
        )
    )
    active_by_media: dict[UUID, Job] = {}
    for job in active_jobs:
        active_by_media.setdefault(job.resource_id, job)

    assessments = list(
        await session.scalars(
            select(MediaSafetyAssessment).where(MediaSafetyAssessment.media_id.in_(media_ids))
        )
    )
    assessment_by_media = {assessment.media_id: assessment for assessment in assessments}
    new_jobs: list[tuple[Job, MediaSafetyAssessment]] = []
    response_job_ids: list[UUID] = []
    reused_count = 0
    skipped_count = 0

    for media_id in media_ids:
        media = by_id.get(media_id)
        if (
            media is None
            or media.kind != "image"
            or media.status not in CLASSIFIABLE_MEDIA_STATUSES
        ):
            skipped_count += 1
            continue
        active_job = active_by_media.get(media_id)
        if active_job is not None:
            response_job_ids.append(active_job.id)
            reused_count += 1
            continue

        assessment = assessment_by_media.get(media_id)
        if (
            not request.force
            and assessment is not None
            and assessment.status == "completed"
            and assessment_matches_settings(assessment, settings)
        ):
            skipped_count += 1
            continue

        job = Job(
            id=uuid7(),
            kind=CLASSIFICATION_JOB_KIND,
            queue="nsfw",
            resource_type="media",
            resource_id=media_id,
            progress_total=1,
        )
        if assessment is None:
            assessment = MediaSafetyAssessment(
                media_id=media_id,
                model_id=settings.nsfw_model_id,
                model_revision=settings.nsfw_model_revision,
            )
            session.add(assessment)
            assessment_by_media[media_id] = assessment
        else:
            _reset_assessment(
                assessment,
                model_id=settings.nsfw_model_id,
                model_revision=settings.nsfw_model_revision,
            )
        assessment.job_id = job.id
        assessment.status = "queued"
        session.add(job)
        new_jobs.append((job, assessment))
        response_job_ids.append(job.id)

    await session.commit()
    queued_count = 0
    queue_failed_count = 0
    for job, assessment in new_jobs:
        try:
            enqueue_nsfw_classification(media_id=str(job.resource_id), job_id=str(job.id))
            queued_count += 1
        except Exception:
            now = datetime.now(UTC)
            job.status = "failed"
            job.error_code = "QUEUE_UNAVAILABLE"
            job.error_message = "The NSFW classification job could not be queued."
            job.error_details = {"retryable": True}
            job.completed_at = now
            assessment.status = "failed"
            assessment.error_code = "QUEUE_UNAVAILABLE"
            assessment.error_message = job.error_message
            assessment.completed_at = now
            queue_failed_count += 1
    if queue_failed_count:
        await session.commit()

    return MediaSafetyClassificationBatchResponse(
        requested_count=len(media_ids),
        queued_count=queued_count,
        reused_count=reused_count,
        skipped_count=skipped_count,
        queue_failed_count=queue_failed_count,
        job_ids=response_job_ids,
    )


@router.get(
    "/{media_id}/nsfw-classification",
    response_model=MediaSafetyClassificationStatusResponse,
)
async def get_media_safety_classification(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> MediaSafetyClassificationStatusResponse:
    media = await session.get(Media, media_id)
    if media is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    assessment = await session.scalar(
        select(MediaSafetyAssessment).where(MediaSafetyAssessment.media_id == media_id)
    )
    job = await session.get(Job, assessment.job_id) if assessment and assessment.job_id else None
    return MediaSafetyClassificationStatusResponse(
        media_id=media_id,
        assessment=(
            MediaSafetyAssessmentResponse.model_validate(assessment) if assessment else None
        ),
        job=JobResponse.model_validate(job) if job is not None else None,
    )


def _require_classifier_enabled(enabled: bool) -> None:
    if not enabled:
        raise ApiError(
            status_code=503,
            code="NSFW_CLASSIFIER_DISABLED",
            message="NSFW classification is disabled by server configuration.",
        )


def _reset_assessment(
    assessment: MediaSafetyAssessment,
    *,
    model_id: str,
    model_revision: str,
) -> None:
    assessment.model_id = model_id
    assessment.model_revision = model_revision
    assessment.label = None
    assessment.suggested_rating = None
    assessment.confidence = None
    assessment.margin = None
    assessment.scores = {}
    assessment.needs_review = False
    assessment.inference_backend = "unknown"
    assessment.nudity_detector_status = "disabled"
    assessment.nudity_detector_mode = "disabled"
    assessment.nudity_detected = False
    assessment.nudity_model_id = None
    assessment.nudity_model_revision = None
    assessment.nudity_detections = []
    assessment.error_code = None
    assessment.error_message = None
    assessment.started_at = None
    assessment.completed_at = None
