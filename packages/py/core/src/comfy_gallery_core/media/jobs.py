from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.db.models import Job, JobStageAttempt
from comfy_gallery_core.media.errors import IngestionError


async def begin_job(session: AsyncSession, job: Job) -> bool:
    if job.status == "succeeded":
        return False
    if job.cancel_requested:
        job.status = "cancelled"
        job.completed_at = datetime.now(UTC)
        await session.commit()
        return False
    job.status = "running"
    job.attempt_count += 1
    job.started_at = job.started_at or datetime.now(UTC)
    job.completed_at = None
    job.error_code = None
    job.error_message = None
    job.error_details = {}
    await session.commit()
    return True


async def begin_stage(
    session: AsyncSession,
    job: Job,
    stage: str,
) -> JobStageAttempt:
    job.stage = stage
    attempt = JobStageAttempt(
        job_id=job.id,
        stage=stage,
        job_attempt=job.attempt_count,
        status="running",
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt)
    return attempt


async def complete_stage(
    session: AsyncSession,
    attempt: JobStageAttempt,
) -> None:
    attempt.status = "succeeded"
    attempt.completed_at = datetime.now(UTC)
    await session.commit()


async def fail_stage(
    session: AsyncSession,
    attempt: JobStageAttempt,
    error: IngestionError,
) -> None:
    attempt.status = "failed"
    attempt.completed_at = datetime.now(UTC)
    attempt.error_code = error.code
    attempt.error_message = error.message
    attempt.error_details = {**error.details, "retryable": error.retryable}
    await session.commit()


async def succeed_job(session: AsyncSession, job: Job) -> None:
    job.status = "succeeded"
    job.stage = "complete"
    job.progress_current = job.progress_total or 1
    job.completed_at = datetime.now(UTC)
    await session.commit()


async def fail_job(
    session: AsyncSession,
    job: Job,
    error: IngestionError,
) -> None:
    job.status = "failed"
    job.error_code = error.code
    job.error_message = error.message
    job.error_details = {**error.details, "retryable": error.retryable}
    job.completed_at = datetime.now(UTC)
    await session.commit()


async def load_job(session: AsyncSession, job_id: UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise IngestionError(
            code="JOB_NOT_FOUND",
            message="The requested background job no longer exists.",
        )
    return job
