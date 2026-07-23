from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from comfy_gallery_api.dependencies import DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    DerivativeResponse,
    MediaDetailResponse,
    MediaListItemResponse,
    MediaPageResponse,
    SourceOccurrenceResponse,
)
from comfy_gallery_core.db.models import Evaluation, Media, SourceOccurrence, WorkflowSnapshot
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("", response_model=MediaPageResponse)
async def list_media(
    _principal: PrincipalDep,
    session: DbSessionDep,
    kind: str | None = None,
    media_status: str | None = Query(default=None, alias="status"),
    workflow_status: str | None = None,
    evaluation_state: str | None = None,
    trash: bool | None = None,
    source_root_id: UUID | None = None,
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MediaPageResponse:
    filters = []
    if kind:
        filters.append(Media.kind == kind)
    if media_status:
        filters.append(Media.status == media_status)
    if workflow_status == "unprocessed":
        filters.append(~Media.workflow_snapshot.has())
    elif workflow_status:
        filters.append(
            Media.workflow_snapshot.has(WorkflowSnapshot.parse_status == workflow_status)
        )
    if evaluation_state == "not_started":
        filters.append(
            or_(
                ~Media.evaluations.any(Evaluation.evaluation_kind == "base"),
                Media.evaluations.any(
                    and_(
                        Evaluation.evaluation_kind == "base",
                        Evaluation.progress_state == "not_started",
                    )
                ),
            )
        )
    elif evaluation_state:
        filters.append(
            Media.evaluations.any(
                and_(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.progress_state == evaluation_state,
                )
            )
        )
    if trash is True:
        filters.append(
            Media.evaluations.any(
                and_(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.is_trash.is_(True),
                )
            )
        )
    elif trash is False:
        filters.append(
            ~Media.evaluations.any(
                and_(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.is_trash.is_(True),
                )
            )
        )

    id_query = select(Media.id).where(*filters)
    if source_root_id is not None:
        id_query = (
            id_query.join(SourceOccurrence, SourceOccurrence.media_id == Media.id)
            .where(
                SourceOccurrence.source_root_id == source_root_id,
                SourceOccurrence.superseded_at.is_(None),
            )
            .distinct()
        )
    total = int(await session.scalar(select(func.count()).select_from(id_query.subquery())) or 0)
    media_ids = list(
        await session.scalars(
            id_query.order_by(Media.created_at.desc()).offset(offset).limit(limit)
        )
    )
    if not media_ids:
        return MediaPageResponse(items=[], total=total, limit=limit, offset=offset)

    records = list(
        await session.scalars(
            select(Media)
            .options(
                selectinload(Media.asset),
                selectinload(Media.workflow_snapshot),
                selectinload(Media.evaluations),
            )
            .where(Media.id.in_(media_ids))
            .order_by(Media.created_at.desc())
        )
    )
    source_rows = await session.execute(
        select(SourceOccurrence.media_id, func.count(SourceOccurrence.id))
        .where(
            SourceOccurrence.media_id.in_(media_ids),
            SourceOccurrence.superseded_at.is_(None),
        )
        .group_by(SourceOccurrence.media_id)
    )
    source_counts = {media_id: count for media_id, count in source_rows}
    return MediaPageResponse(
        items=[_list_item(record, source_counts.get(record.id, 0)) for record in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{media_id}", response_model=MediaDetailResponse)
async def get_media(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> MediaDetailResponse:
    media = await _load_media(session, media_id)
    asset = media.asset
    return MediaDetailResponse(
        id=media.id,
        kind=media.kind,
        status=media.status,
        detected_format=media.detected_format,
        mime_type=media.mime_type,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        frame_rate=media.frame_rate,
        container=media.container,
        video_codec=media.video_codec,
        audio_codec=media.audio_codec,
        probe_data=media.probe_data,
        warning_count=media.warning_count,
        last_error_code=media.last_error_code,
        last_error_message=media.last_error_message,
        sha256=asset.sha256,
        byte_size=asset.byte_size,
        original_filename=asset.original_filename,
        original_extension=asset.original_extension,
        created_at=media.created_at,
        updated_at=media.updated_at,
        preview_url=f"/api/v1/media/{media.id}/preview",
        playback_url=f"/api/v1/media/{media.id}/playback",
        original_url=f"/api/v1/media/{media.id}/original",
        workflow_url=f"/api/v1/media/{media.id}/workflow",
        workflow_status=(
            media.workflow_snapshot.parse_status
            if media.workflow_snapshot is not None
            else "unprocessed"
        ),
        evaluation_state=_base_evaluation(media)[0],
        is_trash=_base_evaluation(media)[1],
        derivatives=[DerivativeResponse.model_validate(item) for item in media.derivatives],
        sources=[
            SourceOccurrenceResponse.model_validate(item) for item in media.source_occurrences
        ],
    )


@router.get("/{media_id}/preview", response_class=FileResponse)
async def get_media_preview(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    media = await _load_media(session, media_id)
    derivative = next(
        (item for item in media.derivatives if item.kind in {"thumbnail", "poster"}),
        None,
    )
    if derivative is not None:
        return _file_response(
            settings,
            derivative.managed_path,
            media_type=derivative.mime_type,
        )
    return _file_response(
        settings,
        media.asset.managed_path,
        media_type=media.mime_type or "application/octet-stream",
    )


@router.get("/{media_id}/playback", response_class=FileResponse)
async def get_media_playback(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> FileResponse:
    media = await _load_media(session, media_id)
    proxy = next(
        (item for item in media.derivatives if item.kind == "video_proxy"),
        None,
    )
    if proxy is not None:
        return _file_response(
            settings,
            proxy.managed_path,
            media_type=proxy.mime_type,
        )
    return _file_response(
        settings,
        media.asset.managed_path,
        media_type=media.mime_type or "application/octet-stream",
    )


@router.get("/{media_id}/original", response_class=FileResponse)
async def get_media_original(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
    download: bool = False,
) -> FileResponse:
    media = await _load_media(session, media_id)
    return _file_response(
        settings,
        media.asset.managed_path,
        media_type=media.mime_type or "application/octet-stream",
        filename=media.asset.original_filename if download else None,
    )


async def _load_media(session: DbSessionDep, media_id: UUID) -> Media:
    media = await session.scalar(
        select(Media)
        .options(
            selectinload(Media.asset),
            selectinload(Media.derivatives),
            selectinload(Media.source_occurrences),
            selectinload(Media.workflow_snapshot),
            selectinload(Media.evaluations),
        )
        .where(Media.id == media_id)
    )
    if media is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    return media


def _list_item(media: Media, source_count: int) -> MediaListItemResponse:
    asset = media.asset
    return MediaListItemResponse(
        id=media.id,
        kind=media.kind,
        status=media.status,
        detected_format=media.detected_format,
        mime_type=media.mime_type,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        container=media.container,
        video_codec=media.video_codec,
        warning_count=media.warning_count,
        byte_size=asset.byte_size,
        original_filename=asset.original_filename,
        source_count=source_count,
        workflow_status=(
            media.workflow_snapshot.parse_status
            if media.workflow_snapshot is not None
            else "unprocessed"
        ),
        evaluation_state=_base_evaluation(media)[0],
        is_trash=_base_evaluation(media)[1],
        created_at=media.created_at,
        preview_url=f"/api/v1/media/{media.id}/preview",
    )


def _base_evaluation(media: Media) -> tuple[str, bool]:
    evaluation = next(
        (item for item in media.evaluations if item.evaluation_kind == "base"),
        None,
    )
    if evaluation is None:
        return "not_started", False
    return evaluation.progress_state, evaluation.is_trash


def _file_response(
    settings: SettingsDep,
    relative_path: str,
    *,
    media_type: str,
    filename: str | None = None,
) -> FileResponse:
    try:
        path = safe_managed_path(settings, relative_path)
    except IngestionError as error:
        raise ApiError(
            status_code=500,
            code=error.code,
            message=error.message,
        ) from error
    if not path.is_file():
        raise ApiError(
            status_code=404,
            code="MANAGED_FILE_MISSING",
            message="The managed media file is missing.",
        )
    safe_filename = Path(filename).name if filename else None
    return FileResponse(path, media_type=media_type, filename=safe_filename)
