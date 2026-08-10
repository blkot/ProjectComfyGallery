from datetime import UTC, datetime
from uuid import UUID

import structlog
from dramatiq import actor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.db.models import (
    ExportRun,
    RegistrySyncRun,
    SpatialConversionRun,
    WorkflowInputReference,
    WorkflowSnapshot,
)
from comfy_gallery_core.logging import configure_logging
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import ensure_storage_layout
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
from comfy_gallery_core.media.spatial_conversion import process_spatial_conversion
from comfy_gallery_core.media.variants import process_variant_import
from comfy_gallery_core.operations.exports import create_portable_export
from comfy_gallery_core.queue import enqueue_workflow_input_capture
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
