from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import Job, JobStageAttempt, Media
from comfy_gallery_core.operations.recovery import reconcile_interrupted_jobs


async def test_stale_running_job_is_interrupted_and_requeued() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    calls: list[dict[str, object]] = []

    def enqueue(**kwargs: object) -> str:
        calls.append(kwargs)
        return "message-id"

    async with session_factory() as session:
        media = Media(kind="image", status="ready")
        session.add(media)
        await session.flush()
        job = Job(
            kind="extract_workflow",
            queue="workflow",
            resource_type="media",
            resource_id=media.id,
            status="running",
            attempt_count=1,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        session.add(job)
        await session.flush()
        attempt = JobStageAttempt(
            job_id=job.id,
            stage="extract",
            job_attempt=1,
            status="running",
        )
        session.add(attempt)
        await session.commit()

        summary = await reconcile_interrupted_jobs(
            session,
            settings=Settings(
                running_job_recovery_after_seconds=30,
                queued_job_recovery_after_seconds=10,
            ),
            enqueue=enqueue,
        )
        await session.refresh(job)
        await session.refresh(attempt)
        assert summary.requeued == 1
        assert job.status == "queued"
        assert attempt.status == "interrupted"
        assert calls == [
            {
                "actor_name": "extract_workflow",
                "queue_name": "workflow",
                "args": (str(media.id), str(job.id)),
            }
        ]
    await engine.dispose()


async def test_fresh_running_job_is_not_duplicated() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    calls: list[object] = []
    async with session_factory() as session:
        media = Media(kind="image", status="ready")
        session.add(media)
        await session.flush()
        session.add(
            Job(
                kind="extract_workflow",
                queue="workflow",
                resource_type="media",
                resource_id=media.id,
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        await session.commit()
        summary = await reconcile_interrupted_jobs(
            session,
            settings=Settings(
                running_job_recovery_after_seconds=30,
                queued_job_recovery_after_seconds=10,
            ),
            enqueue=lambda **kwargs: calls.append(kwargs) or "message",
        )
        assert summary.examined == 0
        assert calls == []
    await engine.dispose()
