from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    Derivative,
    Job,
    Media,
    MediaAsset,
    UploadBatch,
    UploadItem,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import (
    GeneratedDerivative,
    check_free_space,
    generate_derivatives,
    hash_file,
    original_extension,
    original_location,
    place_original,
    probe_media,
    safe_managed_path,
    sniff_media,
)
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)
from comfy_gallery_core.workflow.extraction import extract_workflow_for_media


@dataclass(frozen=True, slots=True)
class IngestionOutcome:
    media_id: UUID
    sha256: str
    byte_size: int
    duplicate: bool
    ready_with_warnings: bool


async def process_upload_item(
    session: AsyncSession,
    *,
    upload_item_id: UUID,
    job_id: UUID,
    settings: Settings,
) -> IngestionOutcome:
    item = await session.get(UploadItem, upload_item_id)
    if item is None:
        raise IngestionError(code="UPLOAD_ITEM_NOT_FOUND", message="The upload item was not found.")
    job = await load_job(session, job_id)
    if not await begin_job(session, job):
        if item.media_id is None:
            item.status = "cancelled"
            item.error_code = "JOB_CANCELLED"
            item.error_message = "The upload job was cancelled before processing."
            item.completed_at = datetime.now(UTC)
            await session.commit()
            await refresh_upload_batch(session, item.batch_id)
            raise IngestionError(code="JOB_CANCELLED", message="The upload job was cancelled.")
        media = await session.get(Media, item.media_id)
        asset = await session.get(MediaAsset, item.media_id)
        if media is None or asset is None:
            raise IngestionError(
                code="MEDIA_NOT_FOUND",
                message="The upload references media that no longer exists.",
            )
        return IngestionOutcome(
            media_id=media.id,
            sha256=asset.sha256,
            byte_size=asset.byte_size,
            duplicate=item.status == "duplicate",
            ready_with_warnings=media.status == "ready_with_warnings",
        )

    staged_path = _safe_staging_path(settings, item.staging_path)
    try:
        if not staged_path.exists() and item.media_id is not None:
            outcome = await _resume_existing_media(
                session,
                media_id=item.media_id,
                job=job,
                settings=settings,
            )
        else:
            outcome = await ingest_staged_file(
                session,
                staged_path=staged_path,
                original_filename=item.original_filename,
                job=job,
                settings=settings,
                known_media_id=item.media_id,
                upload_item=item,
            )
        item.media_id = outcome.media_id
        item.status = "duplicate" if outcome.duplicate else "completed"
        item.error_code = None
        item.error_message = None
        item.completed_at = datetime.now(UTC)
        await session.commit()
        await refresh_upload_batch(session, item.batch_id)
        await succeed_job(session, job)
        return outcome
    except IngestionError as error:
        item.status = "failed"
        item.error_code = error.code
        item.error_message = error.message
        item.completed_at = datetime.now(UTC)
        await session.commit()
        await refresh_upload_batch(session, item.batch_id)
        await fail_job(session, job, error)
        raise


async def ingest_staged_file(
    session: AsyncSession,
    *,
    staged_path: Path,
    original_filename: str,
    job: Job,
    settings: Settings,
    known_media_id: UUID | None = None,
    upload_item: UploadItem | None = None,
    precomputed_sha256: str | None = None,
    precomputed_byte_size: int | None = None,
) -> IngestionOutcome:
    hash_attempt = await begin_stage(session, job, "hash_and_validate")
    try:
        if precomputed_sha256 is None or precomputed_byte_size is None:
            sha256, byte_size = await asyncio.to_thread(
                hash_file,
                staged_path,
                chunk_bytes=settings.hash_chunk_bytes,
            )
        else:
            sha256, byte_size = precomputed_sha256, precomputed_byte_size
        signature = await asyncio.to_thread(sniff_media, staged_path)
        await asyncio.to_thread(check_free_space, settings, required_bytes=byte_size)
        await complete_stage(session, hash_attempt)
    except IngestionError as error:
        await fail_stage(session, hash_attempt, error)
        raise

    existing_asset = await session.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))
    duplicate = existing_asset is not None and existing_asset.media_id != known_media_id

    if existing_asset is None:
        store_attempt = await begin_stage(session, job, "store_original")
        try:
            destination, relative_path = original_location(
                sha256=sha256,
                signature=signature,
                settings=settings,
            )
            media = Media(
                kind=signature.kind,
                status="processing",
                detected_format=signature.detected_format,
                mime_type=signature.mime_type,
            )
            asset = MediaAsset(
                media=media,
                sha256=sha256,
                byte_size=byte_size,
                original_filename=_safe_filename(original_filename),
                original_extension=original_extension(original_filename),
                managed_path=relative_path.as_posix(),
            )
            session.add_all((media, asset))
            await session.flush()
            if upload_item is not None:
                upload_item.media_id = media.id
            await session.commit()
            destination, _ = await asyncio.to_thread(
                place_original,
                staged_path=staged_path,
                sha256=sha256,
                signature=signature,
                settings=settings,
            )
            await complete_stage(session, store_attempt)
        except IngestionError as error:
            await fail_stage(session, store_attempt, error)
            raise
    else:
        loaded_media = await session.get(Media, existing_asset.media_id)
        if loaded_media is None:
            raise IngestionError(
                code="MEDIA_IDENTITY_BROKEN",
                message="A stored hash has no owning media record.",
            )
        media = loaded_media
        if upload_item is not None and upload_item.media_id != media.id:
            upload_item.media_id = media.id
            await session.commit()
        destination = safe_managed_path(settings, existing_asset.managed_path)
        destination_exists = await asyncio.to_thread(destination.is_file)
        if not destination_exists:
            staged_exists = await asyncio.to_thread(staged_path.is_file)
            if not staged_exists:
                raise IngestionError(
                    code="MANAGED_ORIGINAL_MISSING",
                    message="The managed original and its staging copy are both missing.",
                    retryable=True,
                )
            destination, _ = await asyncio.to_thread(
                place_original,
                staged_path=staged_path,
                sha256=sha256,
                signature=signature,
                settings=settings,
            )
        else:
            await asyncio.to_thread(staged_path.unlink, missing_ok=True)

    if media.status not in {"ready", "ready_with_warnings"}:
        await _probe_and_derive(
            session,
            media=media,
            source=destination,
            job=job,
            settings=settings,
        )
    elif not await _has_workflow_snapshot(session, media.id):
        await _extract_workflow_only(
            session,
            media=media,
            source=destination,
            job=job,
            settings=settings,
        )

    return IngestionOutcome(
        media_id=media.id,
        sha256=sha256,
        byte_size=byte_size,
        duplicate=duplicate,
        ready_with_warnings=media.status == "ready_with_warnings",
    )


async def _resume_existing_media(
    session: AsyncSession,
    *,
    media_id: UUID,
    job: Job,
    settings: Settings,
) -> IngestionOutcome:
    media = await session.get(Media, media_id)
    asset = await session.get(MediaAsset, media_id)
    if media is None or asset is None:
        raise IngestionError(
            code="MEDIA_NOT_FOUND",
            message="The partially imported media record no longer exists.",
        )
    source = safe_managed_path(settings, asset.managed_path)
    if media.status not in {"ready", "ready_with_warnings"}:
        await _probe_and_derive(
            session,
            media=media,
            source=source,
            job=job,
            settings=settings,
        )
    elif not await _has_workflow_snapshot(session, media.id):
        await _extract_workflow_only(
            session,
            media=media,
            source=source,
            job=job,
            settings=settings,
        )
    return IngestionOutcome(
        media_id=media.id,
        sha256=asset.sha256,
        byte_size=asset.byte_size,
        duplicate=False,
        ready_with_warnings=media.status == "ready_with_warnings",
    )


async def _probe_and_derive(
    session: AsyncSession,
    *,
    media: Media,
    source: Path,
    job: Job,
    settings: Settings,
) -> None:
    probe_attempt = await begin_stage(session, job, "probe_media")
    try:
        probe = await asyncio.to_thread(probe_media, source, settings)
        media.kind = probe.signature.kind
        media.detected_format = probe.signature.detected_format
        media.mime_type = probe.signature.mime_type
        media.width = probe.width
        media.height = probe.height
        media.duration_seconds = probe.duration_seconds
        media.frame_rate = probe.frame_rate
        media.container = probe.container
        media.video_codec = probe.video_codec
        media.audio_codec = probe.audio_codec
        media.probe_data = probe.raw or {}
        media.status = "processing"
        media.last_error_code = None
        media.last_error_message = None
        await session.commit()
        await complete_stage(session, probe_attempt)
    except IngestionError as error:
        media.status = "failed"
        media.last_error_code = error.code
        media.last_error_message = error.message
        await session.commit()
        await fail_stage(session, probe_attempt, error)
        raise

    warning_count = 0
    last_warning: IngestionError | None = None

    workflow_attempt = await begin_stage(session, job, "extract_workflow")
    try:
        workflow = await extract_workflow_for_media(
            session,
            media_id=media.id,
            source=source,
            settings=settings,
            reason="ingestion",
        )
        if workflow.has_warnings:
            warning_count += 1
        await complete_stage(session, workflow_attempt)
    except IngestionError as error:
        warning_count += 1
        last_warning = error
        await fail_stage(session, workflow_attempt, error)

    derivative_attempt = await begin_stage(session, job, "generate_derivatives")
    try:
        generated = await asyncio.to_thread(
            generate_derivatives,
            media_id=str(media.id),
            source=source,
            probe=probe,
            settings=settings,
        )
        for derivative in generated:
            await _upsert_derivative(session, media.id, derivative, settings)
        await complete_stage(session, derivative_attempt)
    except IngestionError as error:
        warning_count += 1
        last_warning = error
        await fail_stage(session, derivative_attempt, error)

    media.status = "ready_with_warnings" if warning_count else "ready"
    media.warning_count = warning_count
    media.last_error_code = last_warning.code if last_warning is not None else None
    media.last_error_message = last_warning.message if last_warning is not None else None
    await session.commit()


async def _extract_workflow_only(
    session: AsyncSession,
    *,
    media: Media,
    source: Path,
    job: Job,
    settings: Settings,
) -> None:
    attempt = await begin_stage(session, job, "extract_workflow")
    try:
        outcome = await extract_workflow_for_media(
            session,
            media_id=media.id,
            source=source,
            settings=settings,
            reason="ingestion_backfill",
        )
        if outcome.has_warnings:
            media.status = "ready_with_warnings"
            media.warning_count = max(media.warning_count, 1)
            await session.commit()
        await complete_stage(session, attempt)
    except IngestionError as error:
        media.status = "ready_with_warnings"
        media.warning_count = max(media.warning_count, 1)
        media.last_error_code = error.code
        media.last_error_message = error.message
        await session.commit()
        await fail_stage(session, attempt, error)


async def _has_workflow_snapshot(session: AsyncSession, media_id: UUID) -> bool:
    return (
        await session.scalar(
            select(WorkflowSnapshot.id).where(WorkflowSnapshot.media_id == media_id)
        )
        is not None
    )


async def _upsert_derivative(
    session: AsyncSession,
    media_id: UUID,
    generated: GeneratedDerivative,
    settings: Settings,
) -> None:
    relative_path = generated.path.relative_to(settings.resolved_managed_root).as_posix()
    record = await session.scalar(
        select(Derivative).where(
            Derivative.media_id == media_id,
            Derivative.kind == generated.kind,
            Derivative.recipe_version == generated.recipe_version,
        )
    )
    if record is None:
        record = Derivative(
            media_id=media_id,
            kind=generated.kind,
            recipe_version=generated.recipe_version,
            managed_path=relative_path,
            mime_type=generated.mime_type,
            byte_size=generated.byte_size,
        )
        session.add(record)
    record.managed_path = relative_path
    record.mime_type = generated.mime_type
    record.byte_size = generated.byte_size
    record.width = generated.width
    record.height = generated.height
    record.container = generated.container
    record.codec = generated.codec


async def refresh_upload_batch(session: AsyncSession, batch_id: UUID) -> None:
    batch = await session.get(UploadBatch, batch_id)
    if batch is None:
        return
    rows = await session.execute(
        select(UploadItem.status, func.count(UploadItem.id))
        .where(UploadItem.batch_id == batch_id)
        .group_by(UploadItem.status)
    )
    counts = {status: count for status, count in rows}
    batch.queued_count = counts.get("queued", 0) + counts.get("processing", 0)
    batch.completed_count = counts.get("completed", 0)
    batch.duplicate_count = counts.get("duplicate", 0)
    batch.failed_count = counts.get("failed", 0) + counts.get("cancelled", 0)
    resolved = batch.completed_count + batch.duplicate_count + batch.failed_count
    if resolved >= batch.total_count:
        batch.status = "completed" if batch.failed_count == 0 else "completed_with_errors"
        batch.completed_at = datetime.now(UTC)
    else:
        batch.status = "processing"
    await session.commit()


def _safe_staging_path(settings: Settings, relative_path: str) -> Path:
    root = settings.resolved_staging_root
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise IngestionError(
            code="STAGING_PATH_INVALID",
            message="The upload staging path is outside the configured root.",
        )
    return candidate


def _safe_filename(filename: str) -> str:
    normalized = Path(filename).name.strip()
    return normalized[:1024] if normalized else "unnamed-media"
