from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    ExportRun,
    Job,
    JobStageAttempt,
    MediaVariant,
    RegistrySyncRun,
    ScanBatch,
    UploadItem,
)
from comfy_gallery_core.queue import enqueue_message

Enqueue = Callable[..., str]


@dataclass(frozen=True, slots=True)
class RecoverySummary:
    examined: int
    requeued: int
    failed: int


def _dispatch_for(job: Job) -> tuple[str, str, tuple[str, ...]] | None:
    resource_id = str(job.resource_id)
    job_id = str(job.id)
    dispatches = {
        "process_upload": ("process_upload_item", "media", (resource_id, job_id)),
        "process_variant_import": (
            "process_variant_import",
            "media",
            (resource_id, job_id),
        ),
        "scan_source_root": ("scan_source_root", "scan", (resource_id, job_id)),
        "extract_workflow": ("extract_workflow", "workflow", (resource_id, job_id)),
        "registry_sync": ("sync_registry", "registry", (resource_id, job_id)),
        "portable_export": (
            "create_portable_export",
            "maintenance",
            (resource_id, job_id),
        ),
    }
    return dispatches.get(job.kind)


async def _reset_owner(session: AsyncSession, job: Job) -> None:
    owner: object | None = None
    if job.kind == "process_upload":
        owner = await session.get(UploadItem, job.resource_id)
    elif job.kind == "process_variant_import":
        owner = await session.get(MediaVariant, job.resource_id)
    elif job.kind == "scan_source_root":
        owner = await session.get(ScanBatch, job.resource_id)
    elif job.kind == "registry_sync":
        owner = await session.get(RegistrySyncRun, job.resource_id)
    elif job.kind == "portable_export":
        owner = await session.get(ExportRun, job.resource_id)
    if isinstance(owner, MediaVariant):
        if not owner.is_active:
            owner.status = "staging"
        owner.last_error_code = None
        owner.last_error_message = None
    elif isinstance(owner, (UploadItem, ScanBatch, RegistrySyncRun, ExportRun)):
        owner.status = "queued"
        owner.error_code = None
        owner.error_message = None
        owner.completed_at = None


async def reconcile_interrupted_jobs(
    session: AsyncSession,
    *,
    settings: Settings,
    enqueue: Enqueue = enqueue_message,
) -> RecoverySummary:
    now = datetime.now(UTC)
    queued_cutoff = now - timedelta(seconds=settings.queued_job_recovery_after_seconds)
    running_cutoff = now - timedelta(seconds=settings.running_job_recovery_after_seconds)
    jobs = list(
        await session.scalars(
            select(Job)
            .where(
                or_(
                    (Job.status == "queued") & (Job.created_at < queued_cutoff),
                    (Job.status == "running") & (Job.started_at < running_cutoff),
                )
            )
            .order_by(Job.created_at)
        )
    )
    requeued = 0
    failed = 0
    for job in jobs:
        dispatch = _dispatch_for(job)
        if dispatch is None:
            if job.status == "running":
                job.status = "failed"
                job.error_code = "WORKER_INTERRUPTED"
                job.error_message = "The owning worker stopped before this internal stage finished."
                job.error_details = {"retryable": False}
                job.completed_at = now
                failed += 1
            continue

        running_attempts = list(
            await session.scalars(
                select(JobStageAttempt).where(
                    JobStageAttempt.job_id == job.id,
                    JobStageAttempt.status == "running",
                )
            )
        )
        for attempt in running_attempts:
            attempt.status = "interrupted"
            attempt.completed_at = now
            attempt.error_code = "WORKER_INTERRUPTED"
            attempt.error_message = "The worker stopped before this stage completed."
            attempt.error_details = {"retryable": True}
        job.status = "queued"
        job.completed_at = None
        job.cancel_requested = False
        job.error_code = None
        job.error_message = None
        job.error_details = {}
        await _reset_owner(session, job)
        await session.commit()

        actor_name, queue_name, args = dispatch
        try:
            enqueue(actor_name=actor_name, queue_name=queue_name, args=args)
        except Exception:
            job.status = "failed"
            job.error_code = "QUEUE_UNAVAILABLE"
            job.error_message = "Interrupted work could not be returned to the queue."
            job.error_details = {"retryable": True}
            job.completed_at = now
            await session.commit()
            failed += 1
        else:
            requeued += 1
    if jobs:
        await session.commit()
    return RecoverySummary(examined=len(jobs), requeued=requeued, failed=failed)
