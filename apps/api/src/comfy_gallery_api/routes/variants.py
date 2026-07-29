from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import aiofiles
from fastapi import APIRouter, File, Form, Header, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    JobResponse,
    MediaVariantImportStatusResponse,
    VariantImportAcceptedResponse,
)
from comfy_gallery_core.db.models import Job, Media, MediaAsset, MediaVariant
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import original_extension, safe_managed_path
from comfy_gallery_core.media.variants import SPATIAL_VIDEO_ROLE, variant_staging_path
from comfy_gallery_core.queue import enqueue_variant_import

router = APIRouter(prefix="/api/v1/media", tags=["media variants"])


@router.post(
    "/{media_id}/variant-imports",
    response_model=VariantImportAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def import_media_variant(
    media_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    role: Annotated[str, Form()],
    source_asset_sha256: Annotated[str, Form(min_length=64, max_length=64)],
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=256),
    ],
    converter_name: Annotated[str | None, Form(max_length=128)] = None,
    converter_version: Annotated[str | None, Form(max_length=64)] = None,
) -> VariantImportAcceptedResponse:
    normalized_source_sha = source_asset_sha256.casefold()
    if not _is_sha256(normalized_source_sha):
        raise ApiError(
            status_code=422,
            code="VARIANT_SOURCE_HASH_INVALID",
            message="source_asset_sha256 must be a lowercase or uppercase SHA-256 value.",
        )
    media = await session.get(Media, media_id)
    asset = await session.get(MediaAsset, media_id)
    if media is None or asset is None:
        raise ApiError(status_code=404, code="MEDIA_NOT_FOUND", message="The media was not found.")
    if role != SPATIAL_VIDEO_ROLE:
        raise ApiError(
            status_code=422,
            code="VARIANT_ROLE_UNSUPPORTED",
            message="Only the spatial_video variant role is currently supported.",
        )
    if media.kind != "video":
        raise ApiError(
            status_code=422,
            code="VARIANT_MEDIA_KIND_UNSUPPORTED",
            message="Spatial-video variants can only be attached to video media.",
        )
    if normalized_source_sha != asset.sha256.casefold():
        raise ApiError(
            status_code=409,
            code="VARIANT_SOURCE_MISMATCH",
            message="The submitted source hash does not match the target original.",
        )

    key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    existing = await session.scalar(
        select(MediaVariant).where(MediaVariant.idempotency_key_hash == key_hash)
    )
    if existing is not None:
        try:
            return await _resolve_existing_import(
                session,
                existing=existing,
                media_id=media_id,
                role=role,
                source_sha256=normalized_source_sha,
            )
        finally:
            await file.close()

    filename = Path(file.filename or "spatial-video.mov").name[:1024]
    variant = MediaVariant(
        media_id=media_id,
        role=role,
        status="staging",
        idempotency_key_hash=key_hash,
        original_filename=filename,
        original_extension=original_extension(filename),
        converter_name=_optional_text(converter_name),
        converter_version=_optional_text(converter_version),
        source_asset_sha256=normalized_source_sha,
    )
    session.add(variant)
    try:
        # Keep the idempotency reservation uncommitted until both staging and the
        # durable job exist. Concurrent retries wait on the unique key; a crashed
        # receive rolls back and can be retried with the same command key.
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        existing = await session.scalar(
            select(MediaVariant).where(MediaVariant.idempotency_key_hash == key_hash)
        )
        if existing is None:
            raise ApiError(
                status_code=409,
                code="VARIANT_DUPLICATE_CONFLICT",
                message="The variant import conflicted with an existing request.",
            ) from exc
        try:
            return await _resolve_existing_import(
                session,
                existing=existing,
                media_id=media_id,
                role=role,
                source_sha256=normalized_source_sha,
            )
        finally:
            await file.close()

    destination = variant_staging_path(settings, variant.id)
    try:
        await _receive_variant_upload(file, destination, settings.max_variant_upload_bytes)
    except IngestionError as error:
        await session.rollback()
        raise _api_error(error) from error
    except OSError as exc:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        await session.rollback()
        raise ApiError(
            status_code=500,
            code="VARIANT_UPLOAD_FAILED",
            message="The variant upload could not be staged.",
        ) from exc
    finally:
        await file.close()

    job = Job(
        kind="process_variant_import",
        queue="media",
        resource_type="media_variant",
        resource_id=variant.id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    try:
        enqueue_variant_import(variant_id=str(variant.id), job_id=str(job.id))
    except Exception as exc:
        now = datetime.now(UTC)
        variant.status = "failed"
        variant.last_error_code = "QUEUE_UNAVAILABLE"
        variant.last_error_message = "The variant import could not be queued."
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = variant.last_error_message
        job.error_details = {"retryable": True}
        job.completed_at = now
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The variant import could not be queued. Check Redis and the worker.",
        ) from exc
    return _accepted_response(variant, job)


@router.get(
    "/{media_id}/variant-imports/{variant_id}",
    response_model=MediaVariantImportStatusResponse,
)
async def get_media_variant_import(
    media_id: UUID,
    variant_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> MediaVariantImportStatusResponse:
    variant = await _load_variant(session, media_id=media_id, variant_id=variant_id)
    return MediaVariantImportStatusResponse.model_validate(variant)


@router.get(
    "/{media_id}/variants/{variant_id}/content",
    response_class=FileResponse,
)
async def get_media_variant_content(
    media_id: UUID,
    variant_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    variant = await _load_variant(session, media_id=media_id, variant_id=variant_id)
    if variant.status != "ready" or not variant.is_active or not variant.managed_path:
        raise ApiError(
            status_code=404,
            code="VARIANT_NOT_AVAILABLE",
            message="The requested variant is not an active ready representation.",
        )
    try:
        path = safe_managed_path(settings, variant.managed_path)
    except IngestionError as error:
        raise ApiError(
            status_code=500,
            code=error.code,
            message=error.message,
            details=error.details,
        ) from error
    if not path.is_file():
        raise ApiError(
            status_code=404,
            code="VARIANT_FILE_MISSING",
            message="The active variant file is missing from managed storage.",
        )
    return FileResponse(
        path,
        media_type=variant.mime_type or "application/octet-stream",
        filename=None,
        content_disposition_type="inline",
    )


async def _resolve_existing_import(
    session: DbSessionDep,
    *,
    existing: MediaVariant,
    media_id: UUID,
    role: str,
    source_sha256: str,
) -> VariantImportAcceptedResponse:
    if (
        existing.media_id != media_id
        or existing.role != role
        or existing.source_asset_sha256 != source_sha256
    ):
        raise ApiError(
            status_code=409,
            code="IDEMPOTENCY_KEY_REUSED",
            message="That idempotency key belongs to a different variant import command.",
        )
    job = await session.scalar(
        select(Job)
        .where(
            Job.resource_type == "media_variant",
            Job.resource_id == existing.id,
        )
        .order_by(Job.created_at.desc())
    )
    if job is None:
        raise ApiError(
            status_code=409,
            code="VARIANT_IMPORT_RECEIVING",
            message=(
                "That idempotent variant upload is still being received or did not finish staging."
            ),
        )
    return _accepted_response(existing, job)


async def _load_variant(
    session: DbSessionDep,
    *,
    media_id: UUID,
    variant_id: UUID,
) -> MediaVariant:
    variant = await session.scalar(
        select(MediaVariant).where(
            MediaVariant.id == variant_id,
            MediaVariant.media_id == media_id,
        )
    )
    if variant is None:
        raise ApiError(
            status_code=404,
            code="VARIANT_NOT_FOUND",
            message="The media variant was not found.",
        )
    return variant


async def _receive_variant_upload(
    upload: UploadFile,
    destination: Path,
    maximum_bytes: int,
) -> None:
    await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(destination.unlink, missing_ok=True)
    byte_size = 0
    try:
        async with aiofiles.open(destination, "xb") as handle:
            while chunk := await upload.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > maximum_bytes:
                    raise IngestionError(
                        code="VARIANT_UPLOAD_TOO_LARGE",
                        message="The variant upload exceeds the configured size limit.",
                    )
                await handle.write(chunk)
            await handle.flush()
        await asyncio.to_thread(_fsync_file, destination)
    except IngestionError:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise
    if byte_size == 0:
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        raise IngestionError(
            code="MEDIA_EMPTY",
            message="Empty files cannot be imported as variants.",
        )


def _accepted_response(variant: MediaVariant, job: Job) -> VariantImportAcceptedResponse:
    return VariantImportAcceptedResponse(
        variant=MediaVariantImportStatusResponse.model_validate(variant),
        job=JobResponse.model_validate(job),
    )


def _fsync_file(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _api_error(error: IngestionError) -> ApiError:
    status_code = 413 if error.code == "VARIANT_UPLOAD_TOO_LARGE" else 422
    return ApiError(
        status_code=status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )
