from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from sqlalchemy import select

from comfy_gallery_api.dependencies import (
    CsrfPrincipalDep,
    DbSessionDep,
    PrincipalDep,
    SettingsDep,
)
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.operations_schemas import ExportCreateRequest, ExportResponse
from comfy_gallery_core.db.models import ExportRun, Job
from comfy_gallery_core.operations.exports import safe_export_path
from comfy_gallery_core.queue import enqueue_portable_export

router = APIRouter(prefix="/api/v1/exports", tags=["operations"])


def _response(export_run: ExportRun) -> ExportResponse:
    response = ExportResponse.model_validate(export_run)
    if export_run.status == "succeeded" and export_run.artifact_path:
        response.download_url = f"/api/v1/exports/{export_run.id}/download"
    return response


@router.post("", response_model=ExportResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_export(
    request: ExportCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ExportResponse:
    export_run = ExportRun(
        created_by_user_id=principal.user.id,
        requested_options=request.model_dump(),
    )
    session.add(export_run)
    await session.flush()
    job = Job(
        kind="portable_export",
        queue="maintenance",
        resource_type="export_run",
        resource_id=export_run.id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    try:
        enqueue_portable_export(export_run_id=str(export_run.id), job_id=str(job.id))
    except Exception as exc:
        now = datetime.now(UTC)
        export_run.status = "failed"
        export_run.error_code = "QUEUE_UNAVAILABLE"
        export_run.error_message = "The portable export could not be queued."
        export_run.completed_at = now
        job.status = "failed"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "The portable export could not be queued."
        job.error_details = {"retryable": True}
        job.completed_at = now
        await session.commit()
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="The portable export could not be queued.",
        ) from exc
    await session.refresh(export_run)
    return _response(export_run)


@router.get("", response_model=list[ExportResponse])
async def list_exports(
    _principal: PrincipalDep,
    session: DbSessionDep,
    limit: int = 50,
) -> list[ExportResponse]:
    runs = await session.scalars(
        select(ExportRun).order_by(ExportRun.created_at.desc()).limit(max(1, min(limit, 200)))
    )
    return [_response(run) for run in runs]


@router.get("/{export_id}", response_model=ExportResponse)
async def get_export(
    export_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ExportResponse:
    return _response(await _get_export(session, export_id))


@router.get("/{export_id}/download")
async def download_export(
    export_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    export_run = await _get_export(session, export_id)
    if export_run.status != "succeeded" or not export_run.artifact_path:
        raise ApiError(
            status_code=409,
            code="EXPORT_NOT_READY",
            message="The portable export is not ready to download.",
        )
    path = safe_export_path(settings, export_run.artifact_path)
    if not path.is_file():
        raise ApiError(
            status_code=410,
            code="EXPORT_ARTIFACT_MISSING",
            message="The portable export artifact is no longer present.",
        )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=path.name,
        headers={"Cache-Control": "private, no-store"},
    )


async def _get_export(session: DbSessionDep, export_id: UUID) -> ExportRun:
    export_run = await session.get(ExportRun, export_id)
    if export_run is None:
        raise ApiError(
            status_code=404,
            code="EXPORT_NOT_FOUND",
            message="The portable export was not found.",
        )
    return export_run
