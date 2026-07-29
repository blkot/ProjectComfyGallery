from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import JobResponse
from comfy_gallery_core.db.models import (
    ExportRun,
    Job,
    MediaVariant,
    RegistrySyncRun,
    ScanBatch,
    UploadItem,
)
from comfy_gallery_core.queue import (
    enqueue_portable_export,
    enqueue_registry_sync,
    enqueue_scan,
    enqueue_upload,
    enqueue_variant_import,
    enqueue_workflow,
)

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    _principal: PrincipalDep,
    session: DbSessionDep,
    job_status: str | None = None,
    limit: int = 100,
) -> list[JobResponse]:
    query = select(Job)
    if job_status:
        query = query.where(Job.status == job_status)
    jobs = await session.scalars(
        query.order_by(Job.created_at.desc()).limit(max(1, min(limit, 500)))
    )
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> JobResponse:
    return JobResponse.model_validate(await _get_job(session, job_id))


@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_job(
    job_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> JobResponse:
    job = await _get_job(session, job_id)
    if job.status != "failed":
        raise ApiError(
            status_code=409,
            code="JOB_NOT_RETRYABLE",
            message="Only failed jobs can be retried.",
        )
    retryable = bool(job.error_details.get("retryable", False))
    if not retryable and job.error_code != "QUEUE_UNAVAILABLE":
        raise ApiError(
            status_code=409,
            code="JOB_ERROR_NOT_RETRYABLE",
            message="This failure requires a configuration or file change before another attempt.",
        )
    job.status = "queued"
    job.cancel_requested = False
    job.completed_at = None
    await session.commit()
    try:
        if job.kind == "process_upload":
            item = await session.get(UploadItem, job.resource_id)
            if item is None:
                raise ApiError(
                    status_code=404,
                    code="UPLOAD_ITEM_NOT_FOUND",
                    message="The upload item no longer exists.",
                )
            item.status = "queued"
            item.error_code = None
            item.error_message = None
            await session.commit()
            enqueue_upload(upload_item_id=str(item.id), job_id=str(job.id))
        elif job.kind == "process_variant_import":
            variant = await session.get(MediaVariant, job.resource_id)
            if variant is None:
                raise ApiError(
                    status_code=404,
                    code="VARIANT_NOT_FOUND",
                    message="The media variant no longer exists.",
                )
            if variant.is_active and variant.status == "ready":
                raise ApiError(
                    status_code=409,
                    code="VARIANT_ALREADY_READY",
                    message="The active ready variant does not need to be retried.",
                )
            variant.status = "staging"
            variant.last_error_code = None
            variant.last_error_message = None
            await session.commit()
            enqueue_variant_import(variant_id=str(variant.id), job_id=str(job.id))
        elif job.kind == "scan_source_root":
            scan = await session.get(ScanBatch, job.resource_id)
            if scan is None:
                raise ApiError(
                    status_code=404,
                    code="SCAN_NOT_FOUND",
                    message="The scan batch no longer exists.",
                )
            scan.status = "queued"
            scan.error_code = None
            scan.error_message = None
            await session.commit()
            enqueue_scan(scan_id=str(scan.id), job_id=str(job.id))
        elif job.kind == "extract_workflow":
            enqueue_workflow(media_id=str(job.resource_id), job_id=str(job.id))
        elif job.kind == "registry_sync":
            sync_run = await session.get(RegistrySyncRun, job.resource_id)
            if sync_run is None:
                raise ApiError(
                    status_code=404,
                    code="REGISTRY_SYNC_NOT_FOUND",
                    message="The registry synchronization no longer exists.",
                )
            sync_run.status = "queued"
            sync_run.completed_at = None
            sync_run.error_code = None
            sync_run.error_message = None
            await session.commit()
            enqueue_registry_sync(
                sync_run_id=str(sync_run.id),
                job_id=str(job.id),
            )
        elif job.kind == "portable_export":
            export_run = await session.get(ExportRun, job.resource_id)
            if export_run is None:
                raise ApiError(
                    status_code=404,
                    code="EXPORT_NOT_FOUND",
                    message="The portable export no longer exists.",
                )
            export_run.status = "queued"
            export_run.completed_at = None
            export_run.error_code = None
            export_run.error_message = None
            await session.commit()
            enqueue_portable_export(
                export_run_id=str(export_run.id),
                job_id=str(job.id),
            )
        else:
            raise ApiError(
                status_code=409,
                code="JOB_NOT_RETRYABLE",
                message="This internal item job is retried by its owning scan.",
            )
    except ApiError:
        raise
    except Exception as exc:
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "The retry could not be queued."
        job.completed_at = datetime.now(UTC)
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The retry could not be queued.",
        ) from exc
    await session.refresh(job)
    return JobResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(
    job_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> JobResponse:
    job = await _get_job(session, job_id)
    if job.status not in {"queued", "running"}:
        raise ApiError(
            status_code=409,
            code="JOB_NOT_CANCELLABLE",
            message="Only queued or running jobs can be cancelled.",
        )
    job.cancel_requested = True
    await session.commit()
    await session.refresh(job)
    return JobResponse.model_validate(job)


async def _get_job(session: DbSessionDep, job_id: UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise ApiError(status_code=404, code="JOB_NOT_FOUND", message="The job was not found.")
    return job
