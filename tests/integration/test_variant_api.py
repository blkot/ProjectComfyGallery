import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import Headers, UploadFile
from starlette.responses import FileResponse
from starlette.types import Message, Scope

from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.routes.media import get_media
from comfy_gallery_api.routes.variants import (
    get_media_variant_content,
    import_media_variant,
)
from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import Media, MediaAsset, MediaVariant
from comfy_gallery_core.media.files import ensure_storage_layout


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        minimum_free_bytes=0,
        max_variant_upload_bytes=1024,
    )
    ensure_storage_layout(settings)
    return settings


async def test_variant_upload_is_streamed_durable_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "comfy_gallery_api.routes.variants.enqueue_variant_import",
        lambda *, variant_id, job_id: queued.append((variant_id, job_id)) or "message-id",
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(kind="video", status="ready", duration_seconds=4.0)
        asset = MediaAsset(
            media=media,
            sha256="d" * 64,
            byte_size=100,
            original_filename="source.mp4",
            original_extension="mp4",
            managed_path="originals/dd/source.mp4",
        )
        session.add_all((media, asset))
        await session.commit()
        media_id = media.id
        source_sha256 = asset.sha256

        accepted = await import_media_variant(
            media_id=media_id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
            file=UploadFile(
                file=BytesIO(b"candidate spatial bytes"),
                filename="converted.mov",
                headers=Headers({"content-type": "video/quicktime"}),
            ),
            role="spatial_video",
            source_asset_sha256=source_sha256,
            idempotency_key="conversion-run-42",
            converter_name="spatial-pipeline",
            converter_version="1.2.3",
        )

        staged = settings.resolved_staging_root / "variants" / f"{accepted.variant.id}.upload"
        assert accepted.variant.status == "staging"
        assert accepted.job.kind == "process_variant_import"
        assert staged.read_bytes() == b"candidate spatial bytes"
        assert queued == [(str(accepted.variant.id), str(accepted.job.id))]

        repeated = await import_media_variant(
            media_id=media_id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
            file=UploadFile(file=BytesIO(b"ignored retry body"), filename="retry.mov"),
            role="spatial_video",
            source_asset_sha256=source_sha256,
            idempotency_key="conversion-run-42",
            converter_name=None,
            converter_version=None,
        )
        assert repeated.variant.id == accepted.variant.id
        assert repeated.job.id == accepted.job.id
        assert staged.read_bytes() == b"candidate spatial bytes"
        assert len(queued) == 1

        with pytest.raises(ApiError) as mismatch:
            await import_media_variant(
                media_id=media_id,
                _principal=None,  # type: ignore[arg-type]
                session=session,
                settings=settings,
                file=UploadFile(file=BytesIO(b"wrong"), filename="wrong.mov"),
                role="spatial_video",
                source_asset_sha256="e" * 64,
                idempotency_key="wrong-source",
                converter_name=None,
                converter_version=None,
            )
        assert mismatch.value.code == "VARIANT_SOURCE_MISMATCH"

        settings.max_variant_upload_bytes = 4
        with pytest.raises(ApiError) as too_large:
            await import_media_variant(
                media_id=media_id,
                _principal=None,  # type: ignore[arg-type]
                session=session,
                settings=settings,
                file=UploadFile(file=BytesIO(b"too-large"), filename="large.mov"),
                role="spatial_video",
                source_asset_sha256=source_sha256,
                idempotency_key="retry-after-receive-failure",
                converter_name=None,
                converter_version=None,
            )
        assert too_large.value.code == "VARIANT_UPLOAD_TOO_LARGE"

        settings.max_variant_upload_bytes = 1024
        retried = await import_media_variant(
            media_id=media_id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
            file=UploadFile(file=BytesIO(b"valid retry"), filename="retry.mov"),
            role="spatial_video",
            source_asset_sha256=source_sha256,
            idempotency_key="retry-after-receive-failure",
            converter_name=None,
            converter_version=None,
        )
        assert retried.variant.status == "staging"
        assert len(queued) == 2

    await engine.dispose()


async def test_active_variant_content_supports_http_byte_ranges(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    content = b"0123456789abcdef"
    async with session_factory() as session:
        media = Media(kind="video", status="ready", duration_seconds=1, spatial_available=True)
        session.add(
            MediaAsset(
                media=media,
                sha256="f" * 64,
                byte_size=100,
                original_filename="source.mp4",
                original_extension="mp4",
                managed_path="originals/ff/source.mp4",
            )
        )
        await session.flush()
        relative = Path("variants") / str(media.id) / "spatial_video" / "fixture.mov"
        managed = settings.resolved_managed_root / relative
        managed.parent.mkdir(parents=True, exist_ok=True)
        managed.write_bytes(content)
        variant = MediaVariant(
            media_id=media.id,
            role="spatial_video",
            status="ready",
            is_active=True,
            sha256="1" * 64,
            byte_size=len(content),
            original_filename="fixture.mov",
            original_extension="mov",
            managed_path=relative.as_posix(),
            detected_format="mp4",
            mime_type="video/quicktime",
            duration_seconds=1,
            validation_data={"profile": "fixture"},
            source_asset_sha256="f" * 64,
            ready_at=datetime.now(UTC),
        )
        session.add(variant)
        await session.commit()

        response = await get_media_variant_content(
            media_id=media.id,
            variant_id=variant.id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
        )
        status_code, headers, body = await _render_file_response(
            response,
            range_header="bytes=3-7",
        )

        assert status_code == 206
        assert headers["accept-ranges"] == "bytes"
        assert headers["content-range"] == f"bytes 3-7/{len(content)}"
        assert body == b"34567"

        detail = await get_media(
            media.id,
            None,  # type: ignore[arg-type]
            session,
        )
        assert detail.spatial_available
        assert [item.id for item in detail.variants] == [variant.id]
        assert detail.variants[0].content_url.endswith(f"/variants/{variant.id}/content")
        assert detail.playback_url == f"/api/v1/media/{media.id}/playback"

        variant.is_active = False
        await session.commit()
        with pytest.raises(ApiError) as unavailable:
            await get_media_variant_content(
                media_id=media.id,
                variant_id=variant.id,
                _principal=None,  # type: ignore[arg-type]
                session=session,
                settings=settings,
            )
        assert unavailable.value.code == "VARIANT_NOT_AVAILABLE"

    await engine.dispose()


async def _render_file_response(
    response: FileResponse,
    *,
    range_header: str,
) -> tuple[int, dict[str, str], bytes]:
    messages: list[Message] = []
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/variant",
        "raw_path": b"/variant",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"range", range_header.encode("ascii"))],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }

    async def receive() -> Message:
        await asyncio.sleep(0)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        messages.append(message)

    await response(scope, receive, send)
    start = next(message for message in messages if message["type"] == "http.response.start")
    bodies = [
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    ]
    response_headers = {
        key.decode("latin-1"): value.decode("latin-1") for key, value in start["headers"]
    }
    return int(start["status"]), response_headers, b"".join(bodies)
