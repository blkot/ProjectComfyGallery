from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.evaluation_schemas import (
    MediaArchiveRequest,
    MediaArchiveResponse,
)
from comfy_gallery_api.routes.evaluations import _resolve_membership_media_ids
from comfy_gallery_core.db.models import ExportRun, Job
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.operations.media_archives import (
    MEDIA_ARCHIVE_KIND,
    MEDIA_ARCHIVE_MAX_ITEMS,
    media_archive_path,
)
from comfy_gallery_core.queue import enqueue_media_archive

router = APIRouter(prefix="/api/v1/media", tags=["media downloads"])


def _count(run: ExportRun, key: str) -> int | None:
    value = run.table_counts.get(key)
    return int(value) if isinstance(value, int) else None


def _response(run: ExportRun) -> MediaArchiveResponse:
    response = MediaArchiveResponse(
        id=run.id,
        status=run.status,
        requested_count=_requested_count(run),
        included_count=_count(run, "included_count"),
        skipped_count=_count(run, "skipped_count"),
        byte_size=run.byte_size,
        sha256=run.sha256,
        error_code=run.error_code,
        error_message=run.error_message,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )
    if run.status == "succeeded" and run.artifact_path:
        response.download_url = f"/api/v1/media/bulk/download/{run.id}/download"
    return response


def _requested_count(run: ExportRun) -> int:
    value = run.requested_options.get("media_ids")
    return len(value) if isinstance(value, list) else 0


@router.post(
    "/bulk/download",
    response_model=MediaArchiveResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_media_archive(
    request: MediaArchiveRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> MediaArchiveResponse:
    media_ids = await _resolve_membership_media_ids(session, request)
    if not media_ids:
        raise ApiError(
            status_code=422,
            code="MEDIA_ARCHIVE_EMPTY",
            message="The selected media scope is empty.",
        )
    if len(media_ids) > MEDIA_ARCHIVE_MAX_ITEMS:
        raise ApiError(
            status_code=422,
            code="MEDIA_ARCHIVE_TOO_LARGE",
            message=(
                f"A single archive can contain at most {MEDIA_ARCHIVE_MAX_ITEMS:,} media records."
            ),
        )

    archive = ExportRun(
        created_by_user_id=principal.user.id,
        requested_options={
            "kind": MEDIA_ARCHIVE_KIND,
            "media_ids": [str(media_id) for media_id in media_ids],
        },
    )
    session.add(archive)
    await session.flush()
    job = Job(
        kind=MEDIA_ARCHIVE_KIND,
        queue="maintenance",
        resource_type="export_run",
        resource_id=archive.id,
        progress_total=len(media_ids),
    )
    session.add(job)
    await session.commit()
    try:
        enqueue_media_archive(export_run_id=str(archive.id), job_id=str(job.id))
    except Exception as exc:
        now = datetime.now(UTC)
        archive.status = "failed"
        archive.error_code = "QUEUE_UNAVAILABLE"
        archive.error_message = "The media archive could not be queued."
        archive.completed_at = now
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "The media archive could not be queued."
        job.error_details = {"retryable": True}
        job.completed_at = now
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The media archive could not be queued.",
        ) from exc
    await session.refresh(archive)
    return _response(archive)


@router.get(
    "/bulk/download/{archive_id}",
    response_model=MediaArchiveResponse,
)
async def get_media_archive(
    archive_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> MediaArchiveResponse:
    return _response(await _get_media_archive(session, archive_id))


@router.get("/bulk/download/{archive_id}/download")
async def download_media_archive(
    archive_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    archive = await _get_media_archive(session, archive_id)
    if archive.status != "succeeded" or not archive.artifact_path:
        raise ApiError(
            status_code=409,
            code="MEDIA_ARCHIVE_NOT_READY",
            message="The media archive is not ready to download.",
        )
    try:
        path = media_archive_path(settings, archive)
    except IngestionError as error:
        raise ApiError(
            status_code=404,
            code=error.code,
            message=error.message,
        ) from error
    if not path.is_file():
        raise ApiError(
            status_code=410,
            code="MEDIA_ARCHIVE_ARTIFACT_MISSING",
            message="The media archive artifact is no longer present.",
        )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=path.name,
        headers={"Cache-Control": "private, no-store"},
    )


async def _get_media_archive(session: DbSessionDep, archive_id: UUID) -> ExportRun:
    archive = await session.get(ExportRun, archive_id)
    if archive is None or archive.requested_options.get("kind") != MEDIA_ARCHIVE_KIND:
        raise ApiError(
            status_code=404,
            code="MEDIA_ARCHIVE_NOT_FOUND",
            message="The media archive was not found.",
        )
    return archive
