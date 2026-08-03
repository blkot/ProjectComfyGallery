import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import Job, Media, MediaAsset, MediaVariant
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import ensure_storage_layout
from comfy_gallery_core.media.variants import (
    process_variant_import,
    reconcile_spatial_availability,
    variant_staging_path,
)


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        minimum_free_bytes=0,
    )
    ensure_storage_layout(settings)
    return settings


async def test_variant_activation_replacement_and_reconciliation_preserve_preferences(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(
            kind="video",
            status="ready",
            duration_seconds=8.4,
            favorite=True,
            prefer_spatial_playback=True,
        )
        asset = MediaAsset(
            media=media,
            sha256="a" * 64,
            byte_size=100,
            original_filename="ordinary.mp4",
            original_extension="mp4",
            managed_path="originals/aa/source.mp4",
        )
        source_sha256 = asset.sha256
        session.add_all((media, asset))
        await session.commit()

        first, first_job = await _stored_variant(
            session,
            settings,
            media=media,
            content=b"first spatial representation",
            source_sha256=source_sha256,
        )
        first_outcome = await process_variant_import(
            session,
            variant_id=first.id,
            job_id=first_job.id,
            settings=settings,
        )
        await session.refresh(media)
        await session.refresh(first)

        assert first_outcome.replaced_variant_id is None
        assert first.status == "ready"
        assert first.is_active
        assert media.spatial_available
        assert media.favorite
        assert media.prefer_spatial_playback
        assert media.spatial_view_preferred

        second, second_job = await _stored_variant(
            session,
            settings,
            media=media,
            content=b"replacement spatial representation",
            source_sha256=source_sha256,
        )
        second_outcome = await process_variant_import(
            session,
            variant_id=second.id,
            job_id=second_job.id,
            settings=settings,
        )
        await session.refresh(first)
        await session.refresh(second)

        assert second_outcome.replaced_variant_id == first.id
        assert not first.is_active
        assert first.status == "ready"
        assert second.is_active
        assert second.status == "ready"

        media.spatial_available = False
        await session.commit()
        assert await reconcile_spatial_availability(session, media_id=media.id) == 1
        await session.refresh(media)
        assert media.spatial_available
        assert media.favorite
        assert media.prefer_spatial_playback

        active = list(
            await session.scalars(select(MediaVariant).where(MediaVariant.is_active.is_(True)))
        )
        assert [variant.id for variant in active] == [second.id]

    await engine.dispose()


async def test_failed_replacement_leaves_active_variant_unchanged(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(kind="video", status="ready", duration_seconds=5)
        session.add(
            MediaAsset(
                media=media,
                sha256="b" * 64,
                byte_size=100,
                original_filename="ordinary.mp4",
                original_extension="mp4",
                managed_path="originals/bb/source.mp4",
            )
        )
        await session.commit()
        active, active_job = await _stored_variant(
            session,
            settings,
            media=media,
            content=b"known working spatial bytes",
            source_sha256="b" * 64,
        )
        await process_variant_import(
            session,
            variant_id=active.id,
            job_id=active_job.id,
            settings=settings,
        )

        failed, failed_job = await _stored_variant(
            session,
            settings,
            media=media,
            content=b"wrong source replacement",
            source_sha256="c" * 64,
        )
        with pytest.raises(IngestionError) as raised:
            await process_variant_import(
                session,
                variant_id=failed.id,
                job_id=failed_job.id,
                settings=settings,
            )
        await session.refresh(active)
        await session.refresh(failed)
        await session.refresh(media)

        assert raised.value.code == "VARIANT_SOURCE_MISMATCH"
        assert active.is_active
        assert active.status == "ready"
        assert failed.status == "failed"
        assert not failed.is_active
        assert media.spatial_available

    await engine.dispose()


async def test_duplicate_active_variant_for_same_media_is_idempotent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(kind="video", status="ready", duration_seconds=5)
        session.add(
            MediaAsset(
                media=media,
                sha256="d" * 64,
                byte_size=100,
                original_filename="ordinary.mp4",
                original_extension="mp4",
                managed_path="originals/dd/source.mp4",
            )
        )
        await session.commit()

        content = b"\x00\x00\x00\x18ftypqt  already attached spatial bytes"
        active, active_job = await _stored_variant(
            session,
            settings,
            media=media,
            content=content,
            source_sha256="d" * 64,
        )
        await process_variant_import(
            session,
            variant_id=active.id,
            job_id=active_job.id,
            settings=settings,
        )
        duplicate, duplicate_job = await _staged_variant(
            session,
            settings,
            media=media,
            content=content,
            source_sha256="d" * 64,
        )

        outcome = await process_variant_import(
            session,
            variant_id=duplicate.id,
            job_id=duplicate_job.id,
            settings=settings,
        )
        await session.refresh(active)
        await session.refresh(duplicate)
        await session.refresh(duplicate_job)
        await session.refresh(media)

        assert outcome.variant_id == active.id
        assert active.status == "ready"
        assert active.is_active
        assert duplicate.status == "duplicate"
        assert not duplicate.is_active
        assert duplicate.last_error_code is None
        assert duplicate.validation_data == {"duplicate_of_variant_id": str(active.id)}
        assert duplicate_job.status == "succeeded"
        assert media.spatial_available
        assert not variant_staging_path(settings, duplicate.id).exists()

        replay = await process_variant_import(
            session,
            variant_id=duplicate.id,
            job_id=duplicate_job.id,
            settings=settings,
        )
        assert replay.variant_id == active.id

    await engine.dispose()


async def test_duplicate_variant_bytes_for_different_media_remain_a_conflict(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        first_media = Media(kind="video", status="ready", duration_seconds=5)
        second_media = Media(kind="video", status="ready", duration_seconds=5)
        session.add_all(
            (
                MediaAsset(
                    media=first_media,
                    sha256="e" * 64,
                    byte_size=100,
                    original_filename="first.mp4",
                    original_extension="mp4",
                    managed_path="originals/ee/source.mp4",
                ),
                MediaAsset(
                    media=second_media,
                    sha256="f" * 64,
                    byte_size=100,
                    original_filename="second.mp4",
                    original_extension="mp4",
                    managed_path="originals/ff/source.mp4",
                ),
            )
        )
        await session.commit()

        content = b"\x00\x00\x00\x18ftypqt  shared spatial bytes"
        active, active_job = await _stored_variant(
            session,
            settings,
            media=first_media,
            content=content,
            source_sha256="e" * 64,
        )
        await process_variant_import(
            session,
            variant_id=active.id,
            job_id=active_job.id,
            settings=settings,
        )
        conflicting, conflicting_job = await _staged_variant(
            session,
            settings,
            media=second_media,
            content=content,
            source_sha256="f" * 64,
        )

        with pytest.raises(IngestionError) as raised:
            await process_variant_import(
                session,
                variant_id=conflicting.id,
                job_id=conflicting_job.id,
                settings=settings,
            )
        await session.refresh(active)
        await session.refresh(conflicting)
        await session.refresh(conflicting_job)

        assert raised.value.code == "VARIANT_DUPLICATE_CONFLICT"
        assert active.status == "ready"
        assert active.is_active
        assert conflicting.status == "failed"
        assert conflicting.last_error_code == "VARIANT_DUPLICATE_CONFLICT"
        assert conflicting_job.status == "failed"

    await engine.dispose()


async def _stored_variant(
    session: AsyncSession,
    settings: Settings,
    *,
    media: Media,
    content: bytes,
    source_sha256: str,
) -> tuple[MediaVariant, Job]:
    digest = hashlib.sha256(content).hexdigest()
    relative = Path("variants") / str(media.id) / "spatial_video" / f"{digest}.mp4"
    destination = settings.resolved_managed_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    variant = MediaVariant(
        media_id=media.id,
        role="spatial_video",
        status="staging",
        sha256=digest,
        byte_size=len(content),
        original_filename="spatial.mov",
        original_extension="mov",
        managed_path=relative.as_posix(),
        detected_format="mp4",
        mime_type="video/quicktime",
        width=1920,
        height=1080,
        duration_seconds=media.duration_seconds,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec="hevc",
        probe_data={"fixture": True},
        validation_data={"profile": "test", "secondary_view_decoded": True},
        source_asset_sha256=source_sha256,
    )
    session.add(variant)
    await session.flush()
    job = Job(
        kind="process_variant_import",
        queue="media",
        resource_type="media_variant",
        resource_id=variant.id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    return variant, job


async def _staged_variant(
    session: AsyncSession,
    settings: Settings,
    *,
    media: Media,
    content: bytes,
    source_sha256: str,
) -> tuple[MediaVariant, Job]:
    variant = MediaVariant(
        media_id=media.id,
        role="spatial_video",
        status="staging",
        original_filename="spatial.mov",
        original_extension="mov",
        source_asset_sha256=source_sha256,
    )
    session.add(variant)
    await session.flush()
    staging_path = variant_staging_path(settings, variant.id)
    staging_path.parent.mkdir(parents=True, exist_ok=True)
    staging_path.write_bytes(content)
    job = Job(
        kind="process_variant_import",
        queue="media",
        resource_type="media_variant",
        resource_id=variant.id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    return variant, job
