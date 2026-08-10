from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_api.dependencies import Principal
from comfy_gallery_api.routes.spatial_conversions import (
    create_spatial_conversion,
    refresh_spatial_conversion,
)
from comfy_gallery_api.spatial_conversion_schemas import SpatialConversionCreateRequest
from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    Job,
    Media,
    MediaAsset,
    MediaVariant,
    SpatialConversionRun,
    User,
)
from comfy_gallery_core.media.files import ensure_storage_layout
from comfy_gallery_core.media.spatial_conversion import (
    HttpMssClient,
    MssBatch,
    process_spatial_conversion,
    reconcile_spatial_conversion,
)
from comfy_gallery_core.operations.recovery import reconcile_interrupted_jobs
from comfy_gallery_core.queue import enqueue_message


class FakeMssClient:
    def __init__(self, media_id: str, variant_id: str) -> None:
        self.media_id = media_id
        self.variant_id = variant_id
        self.submissions: list[Path] = []
        self.options: list[dict[str, object]] = []
        self.status_calls = 0
        self.status_payload: dict[str, object] | None = None
        self.publish_calls = 0

    async def submit(
        self,
        *,
        source_path: Path,
        filename: str,
        mime_type: str,
        options: dict[str, object],
    ) -> MssBatch:
        del filename, mime_type
        self.submissions.append(source_path)
        self.options.append(options)
        return MssBatch(
            batch_id="mss-batch-1",
            status_url="http://untrusted.example/status",
            queue_position=2,
            payload={"batch_id": "mss-batch-1", "status": "queued"},
        )

    async def status(self, batch_id: str) -> dict[str, object]:
        assert batch_id == "mss-batch-1"
        self.status_calls += 1
        if self.status_payload is None:
            raise AssertionError("a submission actor must not wait for MSS status")
        return self.status_payload

    async def publish(self, batch_id: str) -> dict[str, object]:
        assert batch_id == "mss-batch-1"
        self.publish_calls += 1
        return {"batch_id": batch_id, "status": "completed"}


async def test_conversion_submission_finishes_without_waiting_for_mss(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        minimum_free_bytes=0,
        mss_base_url="http://mss.test:8000",
        mss_poll_interval_seconds=0.1,
        mss_publish_grace_seconds=5,
    )
    ensure_storage_layout(settings)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    source_relative = "originals/aa/source.mp4"
    source_path = settings.resolved_managed_root / source_relative
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(b"original-video")

    async with session_factory() as session:
        user = User(
            username="admin",
            username_normalized="admin",
            password_hash="test",
        )
        media = Media(kind="video", status="ready", mime_type="video/mp4")
        asset = MediaAsset(
            media=media,
            sha256="a" * 64,
            byte_size=14,
            original_filename="source.mp4",
            original_extension="mp4",
            managed_path=source_relative,
        )
        session.add_all((user, media, asset))
        await session.flush()
        variant = MediaVariant(
            media_id=media.id,
            role="spatial_video",
            status="ready",
            is_active=True,
            sha256="b" * 64,
            byte_size=20,
            original_filename="source_spatial.mov",
            source_asset_sha256=asset.sha256,
        )
        session.add(variant)
        await session.flush()
        run = SpatialConversionRun(
            media_id=media.id,
            created_by_user_id=user.id,
            requested_options={"precision": "float16"},
        )
        session.add(run)
        await session.flush()
        job = Job(
            kind="spatial_conversion",
            queue="spatial",
            resource_type="spatial_conversion_run",
            resource_id=run.id,
            progress_total=1,
        )
        session.add(job)
        await session.commit()

        client = FakeMssClient(str(media.id), str(variant.id))
        await process_spatial_conversion(
            session,
            run_id=run.id,
            job=job,
            settings=settings,
            client=client,
        )

        await session.refresh(run)
        await session.refresh(job)
        await session.refresh(job)
        assert client.submissions == [source_path]
        assert client.options == [{"precision": "float16", "source_media_id": str(media.id)}]
        assert run.status == "processing"
        assert run.mss_batch_id == "mss-batch-1"
        assert run.gallery_variant_id is None
        assert job.status == "succeeded"

        retry_job = Job(
            kind="spatial_conversion",
            queue="spatial",
            resource_type="spatial_conversion_run",
            resource_id=run.id,
            progress_total=1,
        )
        session.add(retry_job)
        await session.commit()
        await process_spatial_conversion(
            session,
            run_id=run.id,
            job=retry_job,
            settings=settings,
            client=client,
        )
        assert client.submissions == [source_path]
        assert retry_job.status == "succeeded"

    await engine.dispose()


async def test_reconciliation_marks_only_cg_ready_published_or_existing_variant_success() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        user = User(username="admin", username_normalized="admin", password_hash="test")
        media = Media(kind="video", status="ready")
        session.add_all((user, media))
        await session.flush()
        variant = MediaVariant(
            media_id=media.id,
            role="spatial_video",
            status="ready",
            is_active=True,
            sha256="c" * 64,
            byte_size=20,
            original_filename="existing.mov",
        )
        run = SpatialConversionRun(
            media_id=media.id,
            created_by_user_id=user.id,
            status="processing",
            mss_batch_id="mss-batch-1",
            previous_variant_id=variant.id,
        )
        session.add_all((variant, run))
        await session.commit()
        client = FakeMssClient(str(media.id), str(variant.id))
        client.status_payload = {
            "status": "completed",
            "files": [
                {
                    "status": "completed",
                    "publish_status": "variant_exists",
                    "gallery_media_id": str(media.id),
                    "gallery_variant_id": str(variant.id),
                }
            ],
        }
        assert (
            await reconcile_spatial_conversion(
                session,
                run_id=run.id,
                settings=Settings(mss_reconciliation_interval_seconds=60),
                client=client,
            )
            is False
        )
        await session.refresh(run)
        assert run.status == "succeeded"
        assert run.gallery_variant_id == variant.id
        assert client.status_calls == 1
        assert (
            await reconcile_spatial_conversion(
                session,
                run_id=run.id,
                settings=Settings(mss_reconciliation_interval_seconds=60),
                client=client,
            )
            is False
        )
        assert client.status_calls == 1
    await engine.dispose()


async def test_reconciliation_cannot_overwrite_authoritative_variant_success() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(username="admin", username_normalized="admin", password_hash="test")
        media = Media(kind="video", status="ready")
        session.add_all((user, media))
        await session.flush()
        run = SpatialConversionRun(
            media_id=media.id,
            created_by_user_id=user.id,
            status="processing",
            mss_batch_id="mss-batch-1",
        )
        session.add(run)
        await session.commit()

        class VariantWinsWhileStatusIsInFlight(FakeMssClient):
            async def status(self, batch_id: str) -> dict[str, object]:
                assert batch_id == "mss-batch-1"
                self.status_calls += 1
                # Model CG's validated variant event committing while the MSS GET
                # is in flight. That success is the lifecycle authority.
                run.status = "succeeded"
                run.gallery_media_id = media.id
                run.completed_at = datetime.now(UTC)
                await session.commit()
                return {
                    "status": "failed",
                    "files": [{"status": "failed", "error": "stale MSS failure"}],
                }

        client = VariantWinsWhileStatusIsInFlight(str(media.id), "unused")
        assert (
            await reconcile_spatial_conversion(
                session,
                run_id=run.id,
                settings=Settings(mss_reconciliation_interval_seconds=60),
                client=client,
            )
            is False
        )
        await session.refresh(run)
        assert run.status == "succeeded"
        assert run.error_code is None
        assert run.error_message is None

    await engine.dispose()


async def test_refresh_of_terminal_conversion_is_idempotent(monkeypatch) -> None:
    queued: list[str] = []
    monkeypatch.setattr(
        "comfy_gallery_api.routes.spatial_conversions.enqueue_spatial_reconciliation",
        lambda *, run_id: queued.append(run_id) or "message-1",
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(username="admin", username_normalized="admin", password_hash="test")
        media = Media(kind="video", status="ready")
        session.add_all((user, media))
        await session.flush()
        run = SpatialConversionRun(
            media_id=media.id,
            created_by_user_id=user.id,
            status="succeeded",
            mss_batch_id="mss-batch-1",
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        await session.commit()

        response = await refresh_spatial_conversion(
            run_id=run.id,
            _principal=Principal(user=user, auth_kind="api_token"),
            session=session,
            settings=Settings(mss_base_url="http://mss.test:8000"),
        )

        assert response.conversion is not None
        assert response.conversion.status == "succeeded"
        assert queued == []

    await engine.dispose()


async def test_http_status_get_has_no_json_argument(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"status": "queued"}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, path: str) -> Response:
            calls.append(("get", path))
            return Response()

    monkeypatch.setattr(
        "comfy_gallery_core.media.spatial_conversion.httpx.AsyncClient",
        lambda **_kwargs: Client(),
    )
    client = HttpMssClient(Settings(mss_base_url="http://mss.test:8000"))
    assert await client.status("batch-1") == {"status": "queued"}
    assert calls == [("get", "/spatial/batches/batch-1")]


def test_delayed_reconciliation_uses_broker_delay_not_message_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class Broker:
        def enqueue(self, message, *, delay=None):
            captured["message"] = message
            captured["delay"] = delay

    monkeypatch.setattr("comfy_gallery_core.queue.configure_broker", lambda: Broker())
    enqueue_message(
        actor_name="reconcile_spatial_conversion",
        queue_name="spatial",
        args=("run-1",),
        delay_ms=30_000,
    )
    message = captured["message"]
    assert captured["delay"] == 30_000
    assert message.options == {}


async def test_create_conversion_reuses_active_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        mss_base_url="http://mss.test:8000",
    )
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "comfy_gallery_api.routes.spatial_conversions.enqueue_spatial_conversion",
        lambda *, run_id, job_id: queued.append((run_id, job_id)) or "message-1",
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="admin",
            username_normalized="admin",
            password_hash="test",
        )
        media = Media(kind="video", status="ready")
        session.add_all((user, media))
        await session.commit()
        principal = Principal(user=user, auth_kind="api_token")

        first = await create_spatial_conversion(
            media_id=media.id,
            request=SpatialConversionCreateRequest(precision="float16"),
            principal=principal,
            session=session,
            settings=settings,
        )
        second = await create_spatial_conversion(
            media_id=media.id,
            request=SpatialConversionCreateRequest(precision="float32"),
            principal=principal,
            session=session,
            settings=settings,
        )

        assert first.conversion is not None
        assert second.conversion is not None
        assert second.conversion.id == first.conversion.id
        assert second.conversion.requested_options == {"precision": "float16"}
        assert len(queued) == 1

    await engine.dispose()


async def test_stale_conversion_with_batch_resumes_polling_instead_of_resubmitting() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    calls: list[dict[str, object]] = []
    async with session_factory() as session:
        user = User(
            username="admin",
            username_normalized="admin",
            password_hash="test",
        )
        media = Media(kind="video", status="ready_with_warnings")
        session.add_all((user, media))
        await session.flush()
        run = SpatialConversionRun(
            media_id=media.id,
            created_by_user_id=user.id,
            status="processing",
            mss_batch_id="existing-batch",
            updated_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        session.add(run)
        await session.flush()
        job = Job(
            kind="spatial_conversion",
            queue="spatial",
            resource_type="spatial_conversion_run",
            resource_id=run.id,
            status="running",
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        session.add(job)
        await session.commit()

        summary = await reconcile_interrupted_jobs(
            session,
            settings=Settings(
                running_job_recovery_after_seconds=30,
                queued_job_recovery_after_seconds=10,
            ),
            enqueue=lambda **kwargs: calls.append(kwargs) or "message-id",
        )

        await session.refresh(run)
        assert summary.requeued == 1
        assert run.status == "processing"
        assert run.mss_batch_id == "existing-batch"
        assert calls == [
            {
                "actor_name": "reconcile_spatial_conversion",
                "queue_name": "spatial",
                "args": (str(run.id),),
            }
        ]
        assert job.status == "succeeded"

    await engine.dispose()
