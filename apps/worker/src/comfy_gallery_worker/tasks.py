import asyncio
import math
from datetime import UTC, datetime
from uuid import UUID

import httpx
import structlog
from dramatiq import actor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from comfy_gallery_core.config import get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.db.models import (
    ExportRun,
    Job,
    JobStageAttempt,
    Media,
    MediaAsset,
    MediaSafetyAssessment,
    RegistrySyncRun,
    SpatialConversionRun,
    WorkflowInputReference,
    WorkflowSnapshot,
)
from comfy_gallery_core.logging import configure_logging
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import ensure_storage_layout, safe_managed_path
from comfy_gallery_core.media.ingestion import process_upload_item
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)
from comfy_gallery_core.media.scan import run_source_scan
from comfy_gallery_core.media.spatial_conversion import (
    process_spatial_conversion,
    reconcile_spatial_conversion,
    request_spatial_publish_retry,
)
from comfy_gallery_core.media.variants import process_variant_import
from comfy_gallery_core.nsfw import assessment_matches_settings
from comfy_gallery_core.operations.exports import create_portable_export
from comfy_gallery_core.operations.media_archives import create_media_archive
from comfy_gallery_core.queue import (
    enqueue_nsfw_classification,
    enqueue_spatial_reconciliation,
    enqueue_workflow_input_capture,
)
from comfy_gallery_core.registry.sync import process_registry_sync_job
from comfy_gallery_core.workflow.extraction import process_workflow_job
from comfy_gallery_core.workflow.input_media import (
    CAPTURABLE_STATUSES,
    create_capture_job_if_needed,
    process_workflow_input_job,
)
from comfy_gallery_worker import __version__
from comfy_gallery_worker.broker import broker as broker

settings = get_settings()
ensure_storage_layout(settings)
configure_logging(
    level=settings.log_level,
    json_logs=settings.environment != "development",
)
logger = structlog.get_logger(__name__)
scan_actor_time_limit_ms = (
    float("inf")
    if settings.scan_actor_time_limit_seconds == 0
    else settings.scan_actor_time_limit_seconds * 1_000
)
spatial_submit_time_limit_ms = int((settings.mss_http_timeout_seconds + 60) * 1_000)
nsfw_actor_time_limit_ms = int((settings.nsfw_request_timeout_seconds + 300) * 1_000)
NSFW_JOB_KIND = "classify_media_nsfw"


@actor(queue_name="system", max_retries=3, min_backoff=1_000)
def healthcheck(correlation_id: str) -> dict[str, str]:
    """Small actor used to verify broker-to-worker execution."""

    logger.info(
        "worker_healthcheck",
        correlation_id=correlation_id,
        version=__version__,
    )
    return {
        "status": "ok",
        "correlation_id": correlation_id,
        "version": __version__,
    }


@actor(
    actor_name="process_upload_item",
    queue_name="media",
    max_retries=2,
    min_backoff=5_000,
)
async def process_upload_item_actor(upload_item_id: str, job_id: str) -> None:
    try:
        media_id = await _process_upload(UUID(upload_item_id), UUID(job_id))
        await _schedule_workflow_input_capture(media_id)
        if settings.nsfw_classifier_enabled and settings.nsfw_auto_classify:
            await _schedule_nsfw_classification(media_id)
    except IngestionError as error:
        logger.error(
            "upload_processing_failed",
            upload_item_id=upload_item_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="classify_media_nsfw",
    queue_name="nsfw",
    max_retries=2,
    min_backoff=15_000,
    time_limit=nsfw_actor_time_limit_ms,
)
async def classify_media_nsfw_actor(media_id: str, job_id: str) -> None:
    try:
        await _process_nsfw_classification(UUID(media_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "nsfw_classification_failed",
            media_id=media_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="process_variant_import",
    queue_name="media",
    max_retries=2,
    min_backoff=5_000,
)
async def process_variant_import_actor(variant_id: str, job_id: str) -> None:
    try:
        await _process_variant_import(UUID(variant_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "variant_processing_failed",
            variant_id=variant_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="process_spatial_conversion",
    queue_name="spatial",
    # Retry is explicit through the durable Job API. Blind broker retry after an
    # ambiguous upload could submit the same expensive GPU work twice.
    max_retries=0,
    time_limit=spatial_submit_time_limit_ms,
)
async def process_spatial_conversion_actor(run_id: str, job_id: str) -> None:
    try:
        await _process_spatial_conversion(UUID(run_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "spatial_conversion_failed",
            run_id=run_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(actor_name="reconcile_spatial_conversion", queue_name="spatial", max_retries=0)
async def reconcile_spatial_conversion_actor(run_id: str) -> None:
    try:
        pending = await _reconcile_spatial_conversion(UUID(run_id))
        if pending:
            enqueue_spatial_reconciliation(
                run_id=run_id,
                delay_ms=settings.mss_reconciliation_interval_seconds * 1_000,
            )
    except IngestionError as error:
        logger.error("spatial_conversion_reconciliation_failed", run_id=run_id, code=error.code)
        enqueue_spatial_reconciliation(
            run_id=run_id,
            delay_ms=settings.mss_reconciliation_interval_seconds * 1_000,
        )


@actor(actor_name="retry_spatial_publish", queue_name="spatial", max_retries=0)
async def retry_spatial_publish_actor(run_id: str) -> None:
    try:
        await _retry_spatial_publish(UUID(run_id))
        enqueue_spatial_reconciliation(run_id=run_id)
    except IngestionError as error:
        logger.error("spatial_publish_retry_failed", run_id=run_id, code=error.code)


@actor(
    actor_name="scan_source_root",
    queue_name="scan",
    max_retries=2,
    min_backoff=10_000,
    time_limit=scan_actor_time_limit_ms,
)
async def scan_source_root_actor(scan_id: str, job_id: str) -> None:
    try:
        await _scan_source(UUID(scan_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "source_scan_failed",
            scan_id=scan_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="extract_workflow",
    queue_name="workflow",
    max_retries=2,
    min_backoff=5_000,
)
async def extract_workflow_actor(media_id: str, job_id: str) -> None:
    try:
        await _extract_workflow(UUID(media_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "workflow_extraction_failed",
            media_id=media_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="capture_workflow_inputs",
    queue_name="workflow",
    max_retries=1,
    min_backoff=10_000,
)
async def capture_workflow_inputs_actor(media_id: str, job_id: str) -> None:
    try:
        await _capture_workflow_inputs(UUID(media_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "workflow_input_capture_failed",
            media_id=media_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="sync_registry",
    queue_name="registry",
    max_retries=1,
    min_backoff=15_000,
)
async def sync_registry_actor(sync_run_id: str, job_id: str) -> None:
    try:
        await _sync_registry(UUID(sync_run_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "registry_sync_failed",
            sync_run_id=sync_run_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="create_portable_export",
    queue_name="maintenance",
    max_retries=2,
    min_backoff=15_000,
)
async def create_portable_export_actor(export_run_id: str, job_id: str) -> None:
    try:
        await _create_portable_export(UUID(export_run_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "portable_export_failed",
            export_run_id=export_run_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


@actor(
    actor_name="create_media_archive",
    queue_name="maintenance",
    max_retries=2,
    min_backoff=15_000,
)
async def create_media_archive_actor(export_run_id: str, job_id: str) -> None:
    try:
        await _create_media_archive(UUID(export_run_id), UUID(job_id))
    except IngestionError as error:
        logger.error(
            "media_archive_failed",
            export_run_id=export_run_id,
            job_id=job_id,
            code=error.code,
            retryable=error.retryable,
        )
        if error.retryable:
            raise


async def _process_upload(upload_item_id: UUID, job_id: UUID) -> UUID:
    database = get_database()
    async with database.session() as session:
        outcome = await process_upload_item(
            session,
            upload_item_id=upload_item_id,
            job_id=job_id,
            settings=settings,
        )
        return outcome.media_id


async def _schedule_nsfw_classification(media_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        media = await session.scalar(
            select(Media).where(Media.id == media_id).with_for_update()
        )
        if (
            media is None
            or media.kind != "image"
            or media.status not in {"ready", "ready_with_warnings"}
        ):
            return
        active_job = await session.scalar(
            select(Job).where(
                Job.kind == NSFW_JOB_KIND,
                Job.resource_type == "media",
                Job.resource_id == media_id,
                Job.status.in_(("queued", "running")),
            )
        )
        if active_job is not None:
            return
        assessment = await session.scalar(
            select(MediaSafetyAssessment).where(MediaSafetyAssessment.media_id == media_id)
        )
        if (
            assessment is not None
            and assessment.status == "completed"
            and assessment_matches_settings(assessment, settings)
        ):
            return
        job = Job(
            id=uuid7(),
            kind=NSFW_JOB_KIND,
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
        else:
            _reset_nsfw_assessment(assessment)
            assessment.model_id = settings.nsfw_model_id
            assessment.model_revision = settings.nsfw_model_revision
        assessment.job_id = job.id
        assessment.status = "queued"
        session.add(job)
        await session.commit()
        try:
            enqueue_nsfw_classification(media_id=str(media_id), job_id=str(job.id))
        except Exception as exc:
            now = datetime.now(UTC)
            job.status = "failed"
            job.error_code = "QUEUE_UNAVAILABLE"
            job.error_message = "The NSFW classification job could not be queued."
            job.error_details = {"retryable": True}
            job.completed_at = now
            assessment.status = "failed"
            assessment.error_code = job.error_code
            assessment.error_message = job.error_message
            assessment.completed_at = now
            await session.commit()
            logger.error(
                "nsfw_classification_queue_failed",
                media_id=str(media_id),
                job_id=str(job.id),
                reason=type(exc).__name__,
            )


async def _process_nsfw_classification(media_id: UUID, job_id: UUID) -> None:
    database = get_database()
    attempt_id: UUID | None = None
    asset_path = None
    try:
        async with database.session() as session:
            job = await load_job(session, job_id)
            if not await begin_job(session, job):
                return
            media = await session.get(Media, media_id)
            asset = await session.get(MediaAsset, media_id)
            assessment = await session.scalar(
                select(MediaSafetyAssessment).where(
                    MediaSafetyAssessment.media_id == media_id
                )
            )
            if media is None or asset is None or assessment is None:
                raise IngestionError(
                    code="NSFW_MEDIA_NOT_FOUND",
                    message="The media or classification record no longer exists.",
                )
            if media.kind != "image" or media.status not in {"ready", "ready_with_warnings"}:
                raise IngestionError(
                    code="NSFW_MEDIA_NOT_CLASSIFIABLE",
                    message="Only ready images can be classified by this model.",
                )
            attempt = await begin_stage(session, job, "classify_image")
            attempt_id = attempt.id
            assessment.job_id = job.id
            assessment.status = "running"
            assessment.started_at = datetime.now(UTC)
            assessment.completed_at = None
            assessment.error_code = None
            assessment.error_message = None
            asset_path = safe_managed_path(settings, asset.managed_path)
            await session.commit()

        if asset_path is None or not asset_path.is_file():
            raise IngestionError(
                code="NSFW_IMAGE_UNAVAILABLE",
                message="The managed image file could not be read for classification.",
                retryable=True,
            )
        if asset_path.stat().st_size > settings.nsfw_max_image_bytes:
            raise IngestionError(
                code="NSFW_IMAGE_TOO_LARGE",
                message=(
                    "The image exceeds the configured classification limit of "
                    f"{settings.nsfw_max_image_bytes // (1024 * 1024)} MiB."
                ),
            )
        image_bytes = await asyncio.to_thread(asset_path.read_bytes)
        try:
            async with httpx.AsyncClient(
                timeout=settings.nsfw_request_timeout_seconds
            ) as client:
                response = await client.post(
                    f"{settings.nsfw_service_url}/classify",
                    content=image_bytes,
                    headers={"Content-Type": "application/octet-stream"},
                )
        except httpx.HTTPError as exc:
            raise IngestionError(
                code="NSFW_SERVICE_UNAVAILABLE",
                message="The NSFW runtime could not be reached.",
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc
        if response.status_code >= 400:
            retryable = response.status_code >= 500 or response.status_code in {408, 429}
            detail = "The NSFW runtime rejected the image."
            try:
                response_detail = response.json().get("detail")
                if isinstance(response_detail, str):
                    detail = response_detail[:500]
            except (ValueError, AttributeError):
                pass
            raise IngestionError(
                code="NSFW_RUNTIME_ERROR",
                message=detail,
                retryable=retryable,
                details={"http_status": response.status_code},
            )
        try:
            result = _validate_nsfw_result(response.json())
        except ValueError as exc:
            raise IngestionError(
                code="NSFW_RESPONSE_INVALID",
                message="The NSFW runtime returned an unreadable response.",
            ) from exc

        async with database.session() as session:
            job = await load_job(session, job_id)
            assessment = await session.scalar(
                select(MediaSafetyAssessment).where(
                    MediaSafetyAssessment.media_id == media_id
                )
            )
            attempt = await session.get(JobStageAttempt, attempt_id) if attempt_id else None
            if assessment is None or attempt is None:
                raise IngestionError(
                    code="NSFW_CLASSIFICATION_STATE_MISSING",
                    message="The classification record disappeared before results were saved.",
                )
            assessment.model_id = result["model_id"]
            assessment.model_revision = result["model_revision"]
            assessment.inference_backend = result["inference_backend"]
            assessment.status = "completed"
            assessment.label = result["label"]
            assessment.suggested_rating = result["suggested_rating"]
            assessment.confidence = result["confidence"]
            assessment.margin = result["margin"]
            assessment.scores = result["scores"]
            assessment.needs_review = result["needs_review"]
            assessment.nudity_detector_status = result["nudity_detector_status"]
            assessment.nudity_detector_mode = result["nudity_detector_mode"]
            assessment.nudity_detected = result["nudity_detected"]
            assessment.nudity_model_id = result["nudity_model_id"]
            assessment.nudity_model_revision = result["nudity_model_revision"]
            assessment.nudity_detections = result["nudity_detections"]
            assessment.error_code = None
            assessment.error_message = None
            assessment.completed_at = datetime.now(UTC)
            await complete_stage(session, attempt)
            await succeed_job(session, job)
    except IngestionError as error:
        async with database.session() as session:
            job = await load_job(session, job_id)
            assessment = await session.scalar(
                select(MediaSafetyAssessment).where(
                    MediaSafetyAssessment.media_id == media_id
                )
            )
            if assessment is not None:
                assessment.status = "failed"
                assessment.error_code = error.code
                assessment.error_message = error.message
                assessment.completed_at = datetime.now(UTC)
            if attempt_id is not None:
                attempt = await session.get(JobStageAttempt, attempt_id)
                if attempt is not None and attempt.status == "running":
                    await fail_stage(session, attempt, error)
            await fail_job(session, job, error)
        raise
    except OSError as exc:
        error = IngestionError(
            code="NSFW_IMAGE_READ_FAILED",
            message="The managed image file could not be read.",
            retryable=True,
            details={"reason": type(exc).__name__},
        )
        async with database.session() as session:
            job = await load_job(session, job_id)
            assessment = await session.scalar(
                select(MediaSafetyAssessment).where(
                    MediaSafetyAssessment.media_id == media_id
                )
            )
            if assessment is not None:
                assessment.status = "failed"
                assessment.error_code = error.code
                assessment.error_message = error.message
                assessment.completed_at = datetime.now(UTC)
            if attempt_id is not None:
                attempt = await session.get(JobStageAttempt, attempt_id)
                if attempt is not None and attempt.status == "running":
                    await fail_stage(session, attempt, error)
            await fail_job(session, job, error)
        raise error from exc


def _validate_nsfw_result(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid classifier response.")
    model_id = payload.get("model_id")
    model_revision = payload.get("model_revision")
    inference_backend = payload.get("inference_backend")
    label = payload.get("label")
    suggested_rating = payload.get("suggested_rating")
    scores = payload.get("scores")
    if (
        not isinstance(model_id, str)
        or not isinstance(model_revision, str)
        or not isinstance(label, str)
        or not isinstance(inference_backend, str)
        or inference_backend not in {"pytorch", "onnx"}
        or not isinstance(suggested_rating, str)
        or suggested_rating not in {"safe", "sexy", "nudity", "explicit", "review"}
        or not isinstance(scores, dict)
    ):
        raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid classifier response.")
    numeric_scores: dict[str, float] = {}
    for key, value in scores.items():
        if (
            not isinstance(key, str)
            or not isinstance(value, (int, float))
            or isinstance(value, bool)
        ):
            raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid classifier scores.")
        score = float(value)
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid classifier scores.")
        numeric_scores[key] = score
    confidence = payload.get("confidence")
    margin = payload.get("margin")
    needs_review = payload.get("needs_review")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not isinstance(margin, (int, float))
        or isinstance(margin, bool)
        or not isinstance(needs_review, bool)
        or not math.isfinite(float(confidence))
        or not math.isfinite(float(margin))
        or not 0 <= float(confidence) <= 1
        or not 0 <= float(margin) <= 1
    ):
        raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid classifier scores.")
    nudity_status = payload.get("nudity_detector_status")
    nudity_mode = payload.get("nudity_detector_mode")
    nudity_detected = payload.get("nudity_detected")
    nudity_model_id = payload.get("nudity_model_id")
    nudity_model_revision = payload.get("nudity_model_revision")
    raw_detections = payload.get("nudity_detections")
    if (
        not isinstance(nudity_status, str)
        or nudity_status not in {"disabled", "skipped", "completed"}
        or not isinstance(nudity_mode, str)
        or nudity_mode not in {"disabled", "always", "risk_or_review"}
        or not isinstance(nudity_detected, bool)
        or not isinstance(raw_detections, list)
        or (nudity_model_id is not None and not isinstance(nudity_model_id, str))
        or (nudity_model_revision is not None and not isinstance(nudity_model_revision, str))
        or (
            nudity_status == "disabled"
            and (
                nudity_mode != "disabled"
                or nudity_model_id is not None
                or nudity_model_revision is not None
            )
        )
        or (
            nudity_status != "disabled"
            and (
                nudity_mode == "disabled"
                or not nudity_model_id
                or not nudity_model_revision
            )
        )
    ):
        raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid NudeNet response.")
    detections: list[dict[str, object]] = []
    for item in raw_detections:
        if not isinstance(item, dict):
            raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid NudeNet detection.")
        detection_label = item.get("class")
        detection_score = item.get("score")
        box = item.get("box")
        if (
            not isinstance(detection_label, str)
            or not isinstance(detection_score, (int, float))
            or isinstance(detection_score, bool)
            or not math.isfinite(float(detection_score))
            or not 0 <= float(detection_score) <= 1
            or not isinstance(box, list)
            or len(box) != 4
            or any(not isinstance(value, int) or isinstance(value, bool) for value in box)
        ):
            raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Invalid NudeNet detection.")
        detections.append(
            {
                "class": detection_label,
                "score": float(detection_score),
                "box": box,
            }
        )
    exposed_region_labels = {
        "ANUS_EXPOSED",
        "BUTTOCKS_EXPOSED",
        "FEMALE_BREAST_EXPOSED",
        "FEMALE_GENITALIA_EXPOSED",
        "MALE_BREAST_EXPOSED",
        "MALE_GENITALIA_EXPOSED",
    }
    has_exposed_region = any(
        detection["class"].upper() in exposed_region_labels
        for detection in detections
    )
    if nudity_detected != has_exposed_region:
        raise IngestionError(
            code="NSFW_RESPONSE_INVALID",
            message="Inconsistent NudeNet exposed-region result.",
        )
    if nudity_status != "completed" and (detections or nudity_detected):
        raise IngestionError(code="NSFW_RESPONSE_INVALID", message="Unexpected NudeNet detections.")
    return {
        "model_id": model_id,
        "model_revision": model_revision,
        "inference_backend": inference_backend,
        "label": label,
        "suggested_rating": suggested_rating,
        "confidence": float(confidence),
        "margin": float(margin),
        "scores": numeric_scores,
        "needs_review": needs_review,
        "nudity_detector_status": nudity_status,
        "nudity_detector_mode": nudity_mode,
        "nudity_detected": nudity_detected,
        "nudity_model_id": nudity_model_id,
        "nudity_model_revision": nudity_model_revision,
        "nudity_detections": detections,
    }


def _reset_nsfw_assessment(assessment: MediaSafetyAssessment) -> None:
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


async def _process_variant_import(variant_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        await process_variant_import(
            session,
            variant_id=variant_id,
            job_id=job_id,
            settings=settings,
        )


async def _process_spatial_conversion(run_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        job = await load_job(session, job_id)
        run = await session.get(SpatialConversionRun, run_id)
        if run is None:
            raise IngestionError(
                code="SPATIAL_CONVERSION_NOT_FOUND",
                message="The spatial conversion request no longer exists.",
            )
        await process_spatial_conversion(
            session,
            run_id=run.id,
            job=job,
            settings=settings,
        )
        await session.refresh(run)
        if run.status == "processing":
            enqueue_spatial_reconciliation(run_id=str(run.id))


async def _reconcile_spatial_conversion(run_id: UUID) -> bool:
    database = get_database()
    async with database.session() as session:
        return await reconcile_spatial_conversion(session, run_id=run_id, settings=settings)


async def _retry_spatial_publish(run_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        await request_spatial_publish_retry(session, run_id=run_id, settings=settings)


async def _scan_source(scan_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        await run_source_scan(
            session,
            scan_id=scan_id,
            job_id=job_id,
            settings=settings,
        )


async def _extract_workflow(media_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        outcome = await process_workflow_job(
            session,
            media_id=media_id,
            job_id=job_id,
            settings=settings,
        )
    if outcome is not None:
        await _schedule_workflow_input_capture(media_id)


async def _capture_workflow_inputs(media_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        await process_workflow_input_job(
            session,
            media_id=media_id,
            job_id=job_id,
            settings=settings,
        )


async def _schedule_workflow_input_capture(media_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        await _reserve_and_enqueue_workflow_input_capture(session, media_id)


async def _sync_registry(sync_run_id: UUID, job_id: UUID) -> None:
    database = get_database()
    should_schedule_captures = False
    async with database.session() as session:
        sync_run = await session.get(RegistrySyncRun, sync_run_id)
        should_schedule_captures = bool(
            sync_run is not None and sync_run.requested_options.get("reprocess_workflows", False)
        )
        await process_registry_sync_job(
            session,
            sync_run_id=sync_run_id,
            job_id=job_id,
            settings=settings,
        )
    if should_schedule_captures:
        await _schedule_all_pending_workflow_input_captures()


async def _schedule_all_pending_workflow_input_captures() -> None:
    database = get_database()
    async with database.session() as session:
        media_ids = list(
            await session.scalars(
                select(WorkflowSnapshot.media_id)
                .join(
                    WorkflowInputReference,
                    WorkflowInputReference.snapshot_id == WorkflowSnapshot.id,
                )
                .where(WorkflowInputReference.status.in_(CAPTURABLE_STATUSES))
                .distinct()
                .order_by(WorkflowSnapshot.media_id)
            )
        )
        for media_id in media_ids:
            await _reserve_and_enqueue_workflow_input_capture(session, media_id)


async def _reserve_and_enqueue_workflow_input_capture(
    session: AsyncSession,
    media_id: UUID,
) -> None:
    reservation = await create_capture_job_if_needed(
        session,
        media_id=media_id,
        settings=settings,
    )
    job = reservation.job
    if job is None or not reservation.created:
        return
    try:
        enqueue_workflow_input_capture(media_id=str(media_id), job_id=str(job.id))
    except Exception as exc:
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "Workflow input capture could not be queued."
        job.error_details = {"retryable": True}
        job.completed_at = datetime.now(UTC)
        await session.commit()
        logger.error(
            "workflow_input_capture_queue_failed",
            media_id=str(media_id),
            job_id=str(job.id),
            reason=type(exc).__name__,
        )


async def _create_portable_export(export_run_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        job = await load_job(session, job_id)
        export_run = await session.get(ExportRun, export_run_id)
        if export_run is None:
            raise IngestionError(
                code="EXPORT_NOT_FOUND",
                message="The portable export request no longer exists.",
            )
        if not await begin_job(session, job):
            return
        attempt = await begin_stage(session, job, "write_bundle")
        try:
            await create_portable_export(
                session,
                export_run=export_run,
                settings=settings,
            )
            await complete_stage(session, attempt)
            await succeed_job(session, job)
        except IngestionError as error:
            export_run.status = "failed"
            export_run.error_code = error.code
            export_run.error_message = error.message
            export_run.completed_at = datetime.now(UTC)
            await session.commit()
            await fail_stage(session, attempt, error)
            await fail_job(session, job, error)
            raise


async def _create_media_archive(export_run_id: UUID, job_id: UUID) -> None:
    database = get_database()
    async with database.session() as session:
        job = await load_job(session, job_id)
        export_run = await session.get(ExportRun, export_run_id)
        if export_run is None:
            raise IngestionError(
                code="MEDIA_ARCHIVE_NOT_FOUND",
                message="The media archive request no longer exists.",
            )
        if not await begin_job(session, job):
            return
        attempt = await begin_stage(session, job, "write_media_archive")
        try:
            await create_media_archive(
                session,
                export_run=export_run,
                job=job,
                settings=settings,
            )
            await complete_stage(session, attempt)
            await succeed_job(session, job)
        except IngestionError as error:
            export_run.status = "failed"
            export_run.error_code = error.code
            export_run.error_message = error.message
            export_run.completed_at = datetime.now(UTC)
            await session.commit()
            await fail_stage(session, attempt, error)
            await fail_job(session, job, error)
            raise
