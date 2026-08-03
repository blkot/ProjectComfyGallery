from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import Job, Media, MediaAsset, MediaVariant
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import (
    ProbeResult,
    check_free_space,
    hash_file,
    place_variant,
    probe_media,
    safe_managed_path,
    sniff_media,
    variant_location,
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
from comfy_gallery_core.media.spatial_video import validate_spatial_video

SPATIAL_VIDEO_ROLE = "spatial_video"


@dataclass(frozen=True, slots=True)
class VariantImportOutcome:
    media_id: UUID
    variant_id: UUID
    replaced_variant_id: UUID | None


def variant_staging_path(settings: Settings, variant_id: UUID) -> Path:
    return settings.resolved_staging_root / "variants" / f"{variant_id}.upload"


async def process_variant_import(
    session: AsyncSession,
    *,
    variant_id: UUID,
    job_id: UUID,
    settings: Settings,
) -> VariantImportOutcome:
    variant = await session.get(MediaVariant, variant_id)
    if variant is None:
        raise IngestionError(
            code="VARIANT_NOT_FOUND",
            message="The media variant import was not found.",
        )
    job = await load_job(session, job_id)
    if variant.status == "duplicate":
        with suppress(OSError):
            await asyncio.to_thread(
                variant_staging_path(settings, variant.id).unlink,
                missing_ok=True,
            )
        await succeed_job(session, job)
        return VariantImportOutcome(
            media_id=variant.media_id,
            variant_id=_duplicate_of_variant_id(variant),
            replaced_variant_id=None,
        )
    if not await begin_job(session, job):
        if variant.status == "ready" and variant.is_active:
            return VariantImportOutcome(
                media_id=variant.media_id,
                variant_id=variant.id,
                replaced_variant_id=None,
            )
        raise IngestionError(
            code="VARIANT_JOB_CANCELLED",
            message="The variant import job was cancelled.",
        )
    if variant.status == "ready" and variant.is_active:
        await succeed_job(session, job)
        return VariantImportOutcome(
            media_id=variant.media_id,
            variant_id=variant.id,
            replaced_variant_id=None,
        )

    variant.status = "processing"
    variant.last_error_code = None
    variant.last_error_message = None
    await session.commit()

    staged_path = variant_staging_path(settings, variant.id)
    try:
        await _validate_source_identity(session, variant)
        if await _managed_variant_is_ready_to_activate(variant, settings):
            replaced = await _activate_variant(session, variant, job)
        else:
            duplicate = await _hash_probe_validate_store(
                session,
                variant=variant,
                job=job,
                staged_path=staged_path,
                settings=settings,
            )
            if duplicate is not None:
                # The successful content resolution must not become a failed
                # import solely because best-effort staging cleanup failed.
                with suppress(OSError):
                    await asyncio.to_thread(staged_path.unlink, missing_ok=True)
                await succeed_job(session, job)
                return VariantImportOutcome(
                    media_id=variant.media_id,
                    variant_id=duplicate.id,
                    replaced_variant_id=None,
                )
            replaced = await _activate_variant(session, variant, job)
        await succeed_job(session, job)
        return VariantImportOutcome(
            media_id=variant.media_id,
            variant_id=variant.id,
            replaced_variant_id=replaced,
        )
    except IngestionError as error:
        await session.rollback()
        variant = await session.get(MediaVariant, variant_id)
        if variant is not None and not variant.is_active:
            variant.status = "failed"
            variant.last_error_code = error.code
            variant.last_error_message = error.message
            await session.commit()
        await fail_job(session, job, error)
        if not error.retryable:
            await asyncio.to_thread(staged_path.unlink, missing_ok=True)
        raise


async def _validate_source_identity(session: AsyncSession, variant: MediaVariant) -> None:
    media = await session.get(Media, variant.media_id)
    asset = await session.get(MediaAsset, variant.media_id)
    if media is None or asset is None:
        raise IngestionError(code="MEDIA_NOT_FOUND", message="The target media was not found.")
    if media.kind != "video":
        raise IngestionError(
            code="VARIANT_MEDIA_KIND_UNSUPPORTED",
            message="Spatial-video variants can only be attached to video media.",
        )
    if variant.role != SPATIAL_VIDEO_ROLE:
        raise IngestionError(
            code="VARIANT_ROLE_UNSUPPORTED",
            message="This variant role is not supported.",
        )
    if variant.source_asset_sha256 != asset.sha256:
        raise IngestionError(
            code="VARIANT_SOURCE_MISMATCH",
            message="The submitted source hash does not match the target original.",
        )


async def _hash_probe_validate_store(
    session: AsyncSession,
    *,
    variant: MediaVariant,
    job: Job,
    staged_path: Path,
    settings: Settings,
) -> MediaVariant | None:
    if not await asyncio.to_thread(staged_path.is_file):
        raise IngestionError(
            code="VARIANT_STAGING_MISSING",
            message="The staged variant upload is missing.",
        )

    hash_attempt = await begin_stage(session, job, "hash_variant")
    try:
        sha256, byte_size = await asyncio.to_thread(
            hash_file,
            staged_path,
            chunk_bytes=settings.hash_chunk_bytes,
        )
        await asyncio.to_thread(check_free_space, settings, required_bytes=byte_size)
        await asyncio.to_thread(sniff_media, staged_path)
        await complete_stage(session, hash_attempt)
    except IngestionError as error:
        await fail_stage(session, hash_attempt, error)
        raise

    duplicate = await session.scalar(
        select(MediaVariant).where(
            MediaVariant.sha256 == sha256,
            MediaVariant.id != variant.id,
        )
    )
    if duplicate is not None:
        if (
            duplicate.media_id == variant.media_id
            and duplicate.role == variant.role
            and duplicate.status == "ready"
            and duplicate.is_active
        ):
            variant.status = "duplicate"
            variant.last_error_code = None
            variant.last_error_message = None
            variant.validation_data = {"duplicate_of_variant_id": str(duplicate.id)}
            await session.commit()
            return duplicate
        raise IngestionError(
            code="VARIANT_DUPLICATE_CONFLICT",
            message="These exact variant bytes were already imported.",
            details={
                "existing_media_id": str(duplicate.media_id),
                "existing_variant_id": str(duplicate.id),
            },
        )

    probe_attempt = await begin_stage(session, job, "probe_variant")
    try:
        probe = await asyncio.to_thread(probe_media, staged_path, settings)
        await complete_stage(session, probe_attempt)
    except IngestionError as error:
        await fail_stage(session, probe_attempt, error)
        raise

    media = await session.get(Media, variant.media_id)
    if media is None:
        raise IngestionError(code="MEDIA_NOT_FOUND", message="The target media was not found.")
    validation_attempt = await begin_stage(session, job, "validate_spatial_variant")
    try:
        validation = await asyncio.to_thread(
            validate_spatial_video,
            staged_path,
            probe=probe,
            original_duration_seconds=media.duration_seconds,
            settings=settings,
        )
        await complete_stage(session, validation_attempt)
    except IngestionError as error:
        await fail_stage(session, validation_attempt, error)
        raise

    _apply_probe_facts(
        variant,
        sha256=sha256,
        byte_size=byte_size,
        probe=probe,
        validation_data=validation.evidence,
    )
    _, relative = variant_location(
        media_id=str(variant.media_id),
        role=variant.role,
        sha256=sha256,
        signature=probe.signature,
        settings=settings,
    )
    variant.managed_path = relative.as_posix()
    await session.commit()

    store_attempt = await begin_stage(session, job, "store_variant")
    try:
        await asyncio.to_thread(
            place_variant,
            staged_path=staged_path,
            media_id=str(variant.media_id),
            role=variant.role,
            sha256=sha256,
            signature=probe.signature,
            settings=settings,
        )
        await complete_stage(session, store_attempt)
    except IngestionError as error:
        await fail_stage(session, store_attempt, error)
        raise
    return None


def _apply_probe_facts(
    variant: MediaVariant,
    *,
    sha256: str,
    byte_size: int,
    probe: ProbeResult,
    validation_data: dict[str, object],
) -> None:
    variant.sha256 = sha256
    variant.byte_size = byte_size
    variant.detected_format = probe.signature.detected_format
    variant.mime_type = probe.signature.mime_type
    variant.width = probe.width
    variant.height = probe.height
    variant.duration_seconds = probe.duration_seconds
    variant.frame_rate = probe.frame_rate
    variant.container = probe.container
    variant.video_codec = probe.video_codec
    variant.audio_codec = probe.audio_codec
    variant.probe_data = probe.raw or {}
    variant.validation_data = validation_data


def _duplicate_of_variant_id(variant: MediaVariant) -> UUID:
    value = variant.validation_data.get("duplicate_of_variant_id")
    if isinstance(value, str):
        with suppress(ValueError):
            return UUID(value)
    return variant.id


async def _managed_variant_is_ready_to_activate(
    variant: MediaVariant,
    settings: Settings,
) -> bool:
    if not variant.managed_path or not variant.sha256 or not variant.validation_data:
        return False
    path = safe_managed_path(settings, variant.managed_path)
    if not await asyncio.to_thread(path.is_file):
        return False
    actual_sha, _ = await asyncio.to_thread(
        hash_file,
        path,
        chunk_bytes=settings.hash_chunk_bytes,
    )
    if actual_sha != variant.sha256:
        raise IngestionError(
            code="VARIANT_STORAGE_FAILED",
            message="The managed variant bytes no longer match their stored hash.",
        )
    return True


async def _activate_variant(
    session: AsyncSession,
    variant: MediaVariant,
    job: Job,
) -> UUID | None:
    attempt = await begin_stage(session, job, "activate_variant")
    try:
        media = await session.scalar(
            select(Media).where(Media.id == variant.media_id).with_for_update()
        )
        if media is None:
            raise IngestionError(code="MEDIA_NOT_FOUND", message="The target media was not found.")
        prior_id = await session.scalar(
            select(MediaVariant.id)
            .where(
                MediaVariant.media_id == variant.media_id,
                MediaVariant.role == variant.role,
                MediaVariant.is_active.is_(True),
                MediaVariant.id != variant.id,
            )
            .with_for_update()
        )
        await session.execute(
            update(MediaVariant)
            .where(
                MediaVariant.media_id == variant.media_id,
                MediaVariant.role == variant.role,
                MediaVariant.is_active.is_(True),
                MediaVariant.id != variant.id,
            )
            .values(is_active=False)
        )
        await session.flush()
        variant.status = "ready"
        variant.is_active = True
        variant.ready_at = datetime.now(UTC)
        variant.last_error_code = None
        variant.last_error_message = None
        media.spatial_available = True
        await session.commit()
        await complete_stage(session, attempt)
        return prior_id
    except IngestionError as error:
        await session.rollback()
        await fail_stage(session, attempt, error)
        raise
    except Exception as exc:
        await session.rollback()
        activation_error = IngestionError(
            code="VARIANT_ACTIVATION_FAILED",
            message="The validated variant could not be activated.",
            retryable=True,
            details={"reason": str(exc)},
        )
        await fail_stage(session, attempt, activation_error)
        raise activation_error from exc


async def reconcile_spatial_availability(
    session: AsyncSession,
    *,
    media_id: UUID | None = None,
) -> int:
    active_ready = exists(
        select(MediaVariant.id).where(
            MediaVariant.media_id == Media.id,
            MediaVariant.role == SPATIAL_VIDEO_ROLE,
            MediaVariant.status == "ready",
            MediaVariant.is_active.is_(True),
        )
    )
    statement = (
        update(Media)
        .where(Media.spatial_available.is_distinct_from(active_ready))
        .values(spatial_available=active_ready)
    )
    if media_id is not None:
        statement = statement.where(Media.id == media_id)
    result = await session.execute(statement)
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)
