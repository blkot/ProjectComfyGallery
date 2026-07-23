import shutil
from pathlib import Path

from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from uuid6 import uuid7

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    Derivative,
    Job,
    Media,
    MediaAsset,
    ScanBatch,
    SourceOccurrence,
    SourceRoot,
)
from comfy_gallery_core.media.files import (
    ensure_storage_layout,
    hash_file,
    original_location,
    sniff_media,
)
from comfy_gallery_core.media.ingestion import ingest_staged_file
from comfy_gallery_core.media.jobs import begin_job
from comfy_gallery_core.media.scan import run_source_scan


def _settings(tmp_path: Path) -> Settings:
    import_root = tmp_path / "imports"
    import_root.mkdir()
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        allowed_source_roots=str(import_root),
        minimum_free_bytes=0,
        thumbnail_max_dimension=256,
    )
    ensure_storage_layout(settings)
    return settings


def _make_image(path: Path, *, color: tuple[int, int, int], size: tuple[int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")


async def test_exact_hash_dedup_preserves_one_immutable_original(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    first_source = tmp_path / "first.png"
    second_source = tmp_path / "same-bytes-different-name.png"
    _make_image(first_source, color=(20, 40, 60), size=(320, 180))
    shutil.copy2(first_source, second_source)

    async with session_factory() as session:
        outcomes = []
        for index, source in enumerate((first_source, second_source), start=1):
            staged = settings.resolved_staging_root / f"{index}.upload"
            shutil.copy2(source, staged)
            job = Job(
                kind="test_ingest",
                queue="test",
                resource_type="test",
                resource_id=uuid7(),
                progress_total=1,
            )
            session.add(job)
            await session.commit()
            assert await begin_job(session, job)
            outcomes.append(
                await ingest_staged_file(
                    session,
                    staged_path=staged,
                    original_filename=source.name,
                    job=job,
                    settings=settings,
                )
            )

        media_count = await session.scalar(select(func.count()).select_from(Media))
        asset = await session.scalar(select(MediaAsset))
        derivative = await session.scalar(select(Derivative))

        assert outcomes[0].media_id.version == 7
        assert not outcomes[0].duplicate
        assert outcomes[1].duplicate
        assert outcomes[0].media_id == outcomes[1].media_id
        assert media_count == 1
        assert asset is not None
        assert derivative is not None
        assert (settings.resolved_managed_root / asset.managed_path).is_file()
        assert (settings.resolved_managed_root / derivative.managed_path).is_file()

    await engine.dispose()


async def test_scan_skips_unchanged_tracks_rename_and_versions_changed_path(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    import_root = settings.allowed_source_root_paths[0]
    first = import_root / "set-a" / "frame.png"
    second = import_root / "set-b" / "frame.png"
    _make_image(first, color=(220, 40, 50), size=(320, 200))
    _make_image(second, color=(30, 180, 90), size=(360, 220))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        root = SourceRoot(name="Golden corpus", path=str(import_root))
        session.add(root)
        await session.commit()

        first_scan = await _run_scan(session, root, settings)
        assert first_scan.status == "completed"
        assert first_scan.discovered_count == 2
        assert first_scan.imported_count == 2

        second_scan = await _run_scan(session, root, settings)
        assert second_scan.skipped_count == 2
        assert second_scan.imported_count == 0

        renamed = first.with_name("renamed.png")
        first.rename(renamed)
        rename_scan = await _run_scan(session, root, settings)
        assert rename_scan.skipped_count == 1
        assert rename_scan.duplicate_count == 1
        assert rename_scan.missing_count == 1
        assert await session.scalar(select(func.count()).select_from(Media)) == 2

        _make_image(second, color=(15, 25, 235), size=(480, 260))
        change_scan = await _run_scan(session, root, settings)
        assert change_scan.imported_count == 1
        assert await session.scalar(select(func.count()).select_from(Media)) == 3

        versions = list(
            await session.scalars(
                select(SourceOccurrence).where(
                    SourceOccurrence.source_root_id == root.id,
                    SourceOccurrence.relative_path == "set-b/frame.png",
                )
            )
        )
        assert len(versions) == 2
        assert sum(version.superseded_at is None for version in versions) == 1
        assert {version.status for version in versions} == {"changed", "present"}

    await engine.dispose()


async def test_retry_finishes_atomic_placement_after_database_was_committed(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "interrupted.png"
    staged = settings.resolved_staging_root / "interrupted.upload"
    _make_image(source, color=(72, 33, 190), size=(300, 200))
    shutil.copy2(source, staged)
    sha256, byte_size = hash_file(staged, chunk_bytes=settings.hash_chunk_bytes)
    signature = sniff_media(staged)
    destination, relative_path = original_location(
        sha256=sha256,
        signature=signature,
        settings=settings,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(
            kind="image",
            status="processing",
            detected_format="png",
            mime_type="image/png",
        )
        session.add(media)
        await session.flush()
        session.add(
            MediaAsset(
                media_id=media.id,
                sha256=sha256,
                byte_size=byte_size,
                original_filename=source.name,
                original_extension="png",
                managed_path=relative_path.as_posix(),
            )
        )
        job = Job(
            kind="test_resume",
            queue="test",
            resource_type="test",
            resource_id=uuid7(),
            progress_total=1,
        )
        session.add(job)
        await session.commit()
        assert not destination.exists()
        assert await begin_job(session, job)

        outcome = await ingest_staged_file(
            session,
            staged_path=staged,
            original_filename=source.name,
            job=job,
            settings=settings,
            known_media_id=media.id,
        )

        assert outcome.media_id == media.id
        assert not outcome.duplicate
        assert destination.is_file()
        assert not staged.exists()
        assert media.status == "ready"
        assert await session.scalar(select(func.count()).select_from(Media)) == 1

    await engine.dispose()


async def _run_scan(
    session: AsyncSession,
    root: SourceRoot,
    settings: Settings,
) -> ScanBatch:
    scan = ScanBatch(source_root_id=root.id)
    session.add(scan)
    await session.flush()
    job = Job(
        kind="scan_source_root",
        queue="scan",
        resource_type="scan_batch",
        resource_id=scan.id,
    )
    session.add(job)
    await session.commit()
    await run_source_scan(
        session,
        scan_id=scan.id,
        job_id=job.id,
        settings=settings,
    )
    await session.refresh(scan)
    return scan
