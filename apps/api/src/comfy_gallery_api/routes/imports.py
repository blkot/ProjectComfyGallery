from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import aiofiles
from fastapi import APIRouter, File, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from uuid6 import uuid7

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    ScanResponse,
    SourceRootCreateRequest,
    SourceRootResponse,
    SourceRootUpdateRequest,
    UploadBatchResponse,
)
from comfy_gallery_core.db.models import Job, ScanBatch, SourceRoot, UploadBatch, UploadItem
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.ingestion import refresh_upload_batch
from comfy_gallery_core.media.scan import validate_source_root_path
from comfy_gallery_core.queue import enqueue_scan, enqueue_upload

router = APIRouter(prefix="/api/v1", tags=["imports"])


@router.get("/source-roots", response_model=list[SourceRootResponse])
async def list_source_roots(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[SourceRootResponse]:
    roots = await session.scalars(select(SourceRoot).order_by(SourceRoot.name))
    return [SourceRootResponse.model_validate(root) for root in roots]


@router.post(
    "/source-roots",
    response_model=SourceRootResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_source_root(
    payload: SourceRootCreateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SourceRootResponse:
    try:
        path = validate_source_root_path(payload.path, settings)
    except IngestionError as error:
        raise _api_error(error, 422) from error
    root = SourceRoot(name=payload.name.strip(), path=str(path))
    session.add(root)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ApiError(
            status_code=409,
            code="SOURCE_ROOT_EXISTS",
            message="That source directory is already registered.",
        ) from exc
    await session.refresh(root)
    return SourceRootResponse.model_validate(root)


@router.patch("/source-roots/{root_id}", response_model=SourceRootResponse)
async def update_source_root(
    root_id: UUID,
    payload: SourceRootUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> SourceRootResponse:
    root = await session.get(SourceRoot, root_id)
    if root is None:
        raise ApiError(
            status_code=404,
            code="SOURCE_ROOT_NOT_FOUND",
            message="The source root was not found.",
        )
    if payload.name is not None:
        root.name = payload.name.strip()
    if payload.enabled is not None:
        root.enabled = payload.enabled
    await session.commit()
    await session.refresh(root)
    return SourceRootResponse.model_validate(root)


@router.post(
    "/source-roots/{root_id}/scans",
    response_model=ScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_source_scan(
    root_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ScanResponse:
    root = await session.get(SourceRoot, root_id)
    if root is None:
        raise ApiError(
            status_code=404,
            code="SOURCE_ROOT_NOT_FOUND",
            message="The source root was not found.",
        )
    if not root.enabled:
        raise ApiError(
            status_code=409,
            code="SOURCE_ROOT_DISABLED",
            message="Enable the source root before scanning it.",
        )
    active = await session.scalar(
        select(ScanBatch).where(
            ScanBatch.source_root_id == root.id,
            ScanBatch.status.in_(("queued", "running")),
        )
    )
    if active is not None:
        raise ApiError(
            status_code=409,
            code="SCAN_ALREADY_RUNNING",
            message="A scan is already queued or running for this source root.",
        )
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
    await session.refresh(scan)
    try:
        enqueue_scan(scan_id=str(scan.id), job_id=str(job.id))
    except Exception as exc:
        scan.status = "failed"
        scan.error_code = "QUEUE_UNAVAILABLE"
        scan.error_message = "The scan could not be queued."
        scan.completed_at = datetime.now(UTC)
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = scan.error_message
        job.completed_at = scan.completed_at
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The scan could not be queued. Check Redis and the worker.",
        ) from exc
    return ScanResponse.model_validate(scan)


@router.get("/scans", response_model=list[ScanResponse])
async def list_scans(
    _principal: PrincipalDep,
    session: DbSessionDep,
    limit: int = 50,
) -> list[ScanResponse]:
    bounded_limit = max(1, min(limit, 200))
    scans = await session.scalars(
        select(ScanBatch).order_by(ScanBatch.created_at.desc()).limit(bounded_limit)
    )
    return [ScanResponse.model_validate(scan) for scan in scans]


@router.get("/scans/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ScanResponse:
    scan = await session.get(ScanBatch, scan_id)
    if scan is None:
        raise ApiError(status_code=404, code="SCAN_NOT_FOUND", message="The scan was not found.")
    return ScanResponse.model_validate(scan)


@router.post(
    "/media/imports",
    response_model=UploadBatchResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_media(
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
    files: Annotated[list[UploadFile], File()],
) -> UploadBatchResponse:
    if not files:
        raise ApiError(
            status_code=422,
            code="UPLOAD_FILES_REQUIRED",
            message="Select at least one media file.",
        )
    if len(files) > 200:
        raise ApiError(
            status_code=422,
            code="UPLOAD_BATCH_TOO_LARGE",
            message="A browser upload batch can contain at most 200 files.",
        )

    batch = UploadBatch(total_count=len(files), status="receiving")
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    for upload in files:
        await _receive_upload(session, batch, upload, settings)

    await refresh_upload_batch(session, batch.id)
    return await _load_upload_batch(session, batch.id)


@router.get("/imports", response_model=list[UploadBatchResponse])
async def list_upload_batches(
    _principal: PrincipalDep,
    session: DbSessionDep,
    limit: int = 30,
) -> list[UploadBatchResponse]:
    bounded_limit = max(1, min(limit, 100))
    batches = await session.scalars(
        select(UploadBatch)
        .options(selectinload(UploadBatch.items))
        .order_by(UploadBatch.created_at.desc())
        .limit(bounded_limit)
    )
    return [UploadBatchResponse.model_validate(batch) for batch in batches]


@router.get("/imports/{batch_id}", response_model=UploadBatchResponse)
async def get_upload_batch(
    batch_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> UploadBatchResponse:
    return await _load_upload_batch(session, batch_id)


async def _receive_upload(
    session: DbSessionDep,
    batch: UploadBatch,
    upload: UploadFile,
    settings: SettingsDep,
) -> None:
    item_id = uuid7()
    filename = Path(upload.filename or "unnamed-media").name[:1024]
    relative_path = Path("uploads") / str(batch.id) / f"{item_id}.upload"
    destination = settings.resolved_staging_root / relative_path
    item = UploadItem(
        id=item_id,
        batch_id=batch.id,
        original_filename=filename,
        staging_path=relative_path.as_posix(),
        status="receiving",
    )
    session.add(item)
    await session.commit()

    byte_size = 0
    job: Job | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(destination, "xb") as handle:
            while chunk := await upload.read(settings.hash_chunk_bytes):
                byte_size += len(chunk)
                if byte_size > settings.max_upload_bytes:
                    raise IngestionError(
                        code="UPLOAD_TOO_LARGE",
                        message="The uploaded file exceeds the configured size limit.",
                    )
                await handle.write(chunk)
        if byte_size == 0:
            raise IngestionError(code="MEDIA_EMPTY", message="Empty files cannot be imported.")
        item.byte_size = byte_size
        item.status = "queued"
        job = Job(
            kind="process_upload",
            queue="media",
            resource_type="upload_item",
            resource_id=item.id,
            progress_total=1,
        )
        session.add(job)
        await session.commit()
        enqueue_upload(upload_item_id=str(item.id), job_id=str(job.id))
    except IngestionError as error:
        destination.unlink(missing_ok=True)
        item.status = "failed"
        item.error_code = error.code
        item.error_message = error.message
        item.completed_at = datetime.now(UTC)
        await session.commit()
    except Exception:
        destination.unlink(missing_ok=True)
        item.status = "failed"
        item.error_code = "UPLOAD_RECEIVE_FAILED"
        item.error_message = "The upload could not be staged or queued."
        item.completed_at = datetime.now(UTC)
        await session.commit()
        if job is not None:
            job.status = "failed"
            job.error_code = "QUEUE_UNAVAILABLE"
            job.error_message = item.error_message
            job.completed_at = item.completed_at
            await session.commit()
    finally:
        await upload.close()


async def _load_upload_batch(
    session: DbSessionDep,
    batch_id: UUID,
) -> UploadBatchResponse:
    batch = await session.scalar(
        select(UploadBatch)
        .options(selectinload(UploadBatch.items))
        .where(UploadBatch.id == batch_id)
    )
    if batch is None:
        raise ApiError(
            status_code=404,
            code="UPLOAD_BATCH_NOT_FOUND",
            message="The upload batch was not found.",
        )
    return UploadBatchResponse.model_validate(batch)


def _api_error(error: IngestionError, status_code: int) -> ApiError:
    return ApiError(
        status_code=status_code,
        code=error.code,
        message=error.message,
        details=error.details,
    )
