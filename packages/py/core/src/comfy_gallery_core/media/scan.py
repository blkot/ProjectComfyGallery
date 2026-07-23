from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    Job,
    ScanBatch,
    SourceOccurrence,
    SourceRoot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import copy_and_hash
from comfy_gallery_core.media.ingestion import IngestionOutcome, ingest_staged_file
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)

SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".@__thumb",  # QNAP Multimedia Console
        ".appledouble",
        ".spotlight-v100",
        ".thumbnails",
        ".trash",
        ".trashes",
        "#recycle",
        "@eadir",  # Synology Media Indexing
        "@recycle",
        "system volume information",
    }
)


async def run_source_scan(
    session: AsyncSession,
    *,
    scan_id: UUID,
    job_id: UUID,
    settings: Settings,
) -> None:
    batch = await session.get(ScanBatch, scan_id)
    if batch is None:
        raise IngestionError(code="SCAN_NOT_FOUND", message="The scan batch was not found.")
    source_root = await session.get(SourceRoot, batch.source_root_id)
    if source_root is None:
        raise IngestionError(
            code="SOURCE_ROOT_NOT_FOUND",
            message="The source root was removed before the scan started.",
        )
    job = await load_job(session, job_id)
    if not await begin_job(session, job):
        batch.status = "cancelled"
        batch.completed_at = datetime.now(UTC)
        await session.commit()
        return

    try:
        root_path = validate_source_root_path(source_root.path, settings)
        batch.status = "running"
        batch.started_at = datetime.now(UTC)
        await session.commit()

        for source_path in iter_media_files(root_path):
            await session.refresh(job)
            if job.cancel_requested:
                job.status = "cancelled"
                job.completed_at = datetime.now(UTC)
                batch.status = "cancelled"
                batch.completed_at = datetime.now(UTC)
                await session.commit()
                return
            await _scan_one_file(
                session,
                source_path=source_path,
                root_path=root_path,
                source_root=source_root,
                batch=batch,
                parent_job=job,
                settings=settings,
            )

        missing = await _mark_missing(session, source_root.id, batch.id)
        batch.missing_count = missing
        batch.status = "completed" if batch.failed_count == 0 else "completed_with_errors"
        batch.completed_at = datetime.now(UTC)
        source_root.last_scan_at = batch.completed_at
        job.progress_total = batch.discovered_count
        job.progress_current = batch.discovered_count
        await session.commit()
        await succeed_job(session, job)
    except IngestionError as error:
        batch.status = "failed"
        batch.error_code = error.code
        batch.error_message = error.message
        batch.completed_at = datetime.now(UTC)
        await session.commit()
        await fail_job(session, job, error)
        raise
    except OSError as exc:
        scan_error = IngestionError(
            code="SOURCE_SCAN_FAILED",
            message="The source directory could not be scanned.",
            retryable=True,
            details={"reason": str(exc)},
        )
        batch.status = "failed"
        batch.error_code = scan_error.code
        batch.error_message = scan_error.message
        batch.completed_at = datetime.now(UTC)
        await session.commit()
        await fail_job(session, job, scan_error)
        raise scan_error from exc


async def _scan_one_file(
    session: AsyncSession,
    *,
    source_path: Path,
    root_path: Path,
    source_root: SourceRoot,
    batch: ScanBatch,
    parent_job: Job,
    settings: Settings,
) -> None:
    relative_path = source_path.relative_to(root_path).as_posix()
    batch.discovered_count += 1
    parent_job.progress_current = batch.discovered_count
    await session.commit()

    try:
        stat = await asyncio.to_thread(source_path.stat, follow_symlinks=False)
    except OSError:
        batch.failed_count += 1
        await session.commit()
        return

    current = await session.scalar(
        select(SourceOccurrence)
        .where(
            SourceOccurrence.source_root_id == source_root.id,
            SourceOccurrence.relative_path == relative_path,
            SourceOccurrence.superseded_at.is_(None),
        )
        .order_by(SourceOccurrence.created_at.desc())
        .limit(1)
    )
    if (
        current is not None
        and current.byte_size == stat.st_size
        and current.mtime_ns == stat.st_mtime_ns
        and current.sha256 is not None
    ):
        current.status = "present"
        current.last_seen_scan_id = batch.id
        current.error_code = None
        current.error_message = None
        batch.skipped_count += 1
        await session.commit()
        return

    item_job = Job(
        kind="ingest_source",
        queue="scan",
        resource_type="source_path",
        resource_id=uuid7(),
        progress_total=1,
    )
    session.add(item_job)
    await session.commit()
    await session.refresh(item_job)
    await begin_job(session, item_job)

    relative_staging = Path("scans") / str(batch.id) / f"{item_job.id}.part"
    staged_path = settings.resolved_staging_root / relative_staging
    copy_attempt = await begin_stage(session, item_job, "stage_source")
    try:
        sha256, byte_size = await asyncio.to_thread(
            copy_and_hash,
            source_path,
            staged_path,
            chunk_bytes=settings.hash_chunk_bytes,
        )
        await complete_stage(session, copy_attempt)
        outcome = await ingest_staged_file(
            session,
            staged_path=staged_path,
            original_filename=source_path.name,
            job=item_job,
            settings=settings,
            known_media_id=current.media_id if current is not None else None,
            precomputed_sha256=sha256,
            precomputed_byte_size=byte_size,
        )
        await _record_occurrence(
            session,
            current=current,
            source_root=source_root,
            batch=batch,
            relative_path=relative_path,
            filename=source_path.name,
            stat=stat,
            outcome=outcome,
        )
        if outcome.duplicate:
            batch.duplicate_count += 1
        else:
            batch.imported_count += 1
        await session.commit()
        await succeed_job(session, item_job)
    except IngestionError as error:
        await asyncio.to_thread(staged_path.unlink, missing_ok=True)
        if copy_attempt.status == "running":
            await fail_stage(session, copy_attempt, error)
        await _record_scan_failure(
            session,
            current=current,
            source_root=source_root,
            batch=batch,
            relative_path=relative_path,
            filename=source_path.name,
            stat=stat,
            error=error,
        )
        batch.failed_count += 1
        await session.commit()
        await fail_job(session, item_job, error)


async def _record_occurrence(
    session: AsyncSession,
    *,
    current: SourceOccurrence | None,
    source_root: SourceRoot,
    batch: ScanBatch,
    relative_path: str,
    filename: str,
    stat: os.stat_result,
    outcome: IngestionOutcome,
) -> None:
    if current is not None and current.sha256 == outcome.sha256:
        current.media_id = outcome.media_id
        current.byte_size = stat.st_size
        current.mtime_ns = stat.st_mtime_ns
        current.status = "present"
        current.last_seen_scan_id = batch.id
        current.error_code = None
        current.error_message = None
        return

    if current is not None:
        current.status = "changed"
        current.superseded_at = datetime.now(UTC)

    session.add(
        SourceOccurrence(
            source_root_id=source_root.id,
            media_id=outcome.media_id,
            relative_path=relative_path,
            original_filename=filename,
            byte_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            sha256=outcome.sha256,
            status="present",
            first_seen_scan_id=batch.id,
            last_seen_scan_id=batch.id,
        )
    )


async def _record_scan_failure(
    session: AsyncSession,
    *,
    current: SourceOccurrence | None,
    source_root: SourceRoot,
    batch: ScanBatch,
    relative_path: str,
    filename: str,
    stat: os.stat_result,
    error: IngestionError,
) -> None:
    if current is not None:
        current.status = "unreadable"
        current.last_seen_scan_id = batch.id
        current.error_code = error.code
        current.error_message = error.message
        return
    session.add(
        SourceOccurrence(
            source_root_id=source_root.id,
            relative_path=relative_path,
            original_filename=filename,
            byte_size=stat.st_size,
            mtime_ns=stat.st_mtime_ns,
            status="unreadable",
            first_seen_scan_id=batch.id,
            last_seen_scan_id=batch.id,
            error_code=error.code,
            error_message=error.message,
        )
    )


async def _mark_missing(
    session: AsyncSession,
    source_root_id: UUID,
    scan_id: UUID,
) -> int:
    records = await session.scalars(
        select(SourceOccurrence).where(
            SourceOccurrence.source_root_id == source_root_id,
            SourceOccurrence.superseded_at.is_(None),
            SourceOccurrence.last_seen_scan_id != scan_id,
            SourceOccurrence.status != "missing",
        )
    )
    missing = list(records)
    for record in missing:
        record.status = "missing"
    await session.commit()
    return len(missing)


def validate_source_root_path(raw_path: str, settings: Settings) -> Path:
    try:
        candidate = Path(raw_path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise IngestionError(
            code="SOURCE_ROOT_UNAVAILABLE",
            message="The source root does not exist or cannot be read.",
            details={"reason": str(exc)},
        ) from exc
    if not candidate.is_dir():
        raise IngestionError(
            code="SOURCE_ROOT_NOT_DIRECTORY",
            message="The configured source root is not a directory.",
        )
    if not any(
        candidate == allowed or candidate.is_relative_to(allowed)
        for allowed in settings.allowed_source_root_paths
    ):
        raise IngestionError(
            code="SOURCE_ROOT_NOT_ALLOWED",
            message="The source root is outside the server's allowed import mounts.",
        )
    for protected in (settings.resolved_managed_root, settings.resolved_staging_root):
        if (
            candidate == protected
            or candidate.is_relative_to(protected)
            or protected.is_relative_to(candidate)
        ):
            raise IngestionError(
                code="SOURCE_ROOT_OVERLAPS_STORAGE",
                message="An import root cannot overlap managed or staging storage.",
            )
    return candidate


def iter_media_files(root: Path) -> Iterator[Path]:
    directories = [root]
    while directories:
        directory = directories.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if is_ignored_source_directory(entry.name):
                        continue
                    directories.append(Path(entry.path))
                    continue
                if (
                    entry.is_file(follow_symlinks=False)
                    and Path(entry.name).suffix.casefold() in SUPPORTED_SUFFIXES
                ):
                    yield Path(entry.path)


def is_ignored_source_directory(name: str) -> bool:
    normalized = name.casefold()
    return normalized in IGNORED_DIRECTORY_NAMES or normalized.startswith(".trash-")
