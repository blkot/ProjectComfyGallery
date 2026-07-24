from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement, Select

from comfy_gallery_api.dependencies import DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    DerivativeResponse,
    MediaDetailResponse,
    MediaListItemResponse,
    MediaNavigationResponse,
    MediaPageResponse,
    SourceOccurrenceResponse,
)
from comfy_gallery_core.db.models import (
    Evaluation,
    Media,
    MediaAsset,
    ModelUsage,
    SourceOccurrence,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path

router = APIRouter(prefix="/api/v1/media", tags=["media"])
MediaSort = Literal[
    "file_created_desc",
    "file_created_asc",
    "imported_desc",
    "imported_asc",
    "filename_asc",
    "filename_desc",
    "size_desc",
    "size_asc",
]


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
    checkpoint_reference_id: UUID | None = None,
    lora_reference_id: UUID | None = None,
    sort: MediaSort = "file_created_desc",
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MediaPageResponse:
    id_query = _media_id_query(
        kind=kind,
        media_status=media_status,
        workflow_status=workflow_status,
        evaluation_state=evaluation_state,
        trash=trash,
        source_root_id=source_root_id,
        checkpoint_reference_id=checkpoint_reference_id,
        lora_reference_id=lora_reference_id,
    )
    total = int(await session.scalar(select(func.count()).select_from(id_query.subquery())) or 0)
    order = _media_order(sort)
    media_ids = list(await session.scalars(id_query.order_by(*order).offset(offset).limit(limit)))
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
        )
    )
    records_by_id = {record.id: record for record in records}
    source_rows = await session.execute(
        select(
            SourceOccurrence.media_id,
            func.count(SourceOccurrence.id),
            func.max(SourceOccurrence.mtime_ns),
        )
        .where(
            SourceOccurrence.media_id.in_(media_ids),
            SourceOccurrence.superseded_at.is_(None),
        )
        .group_by(SourceOccurrence.media_id)
    )
    source_facts = {
        media_id: (int(count), int(maximum_mtime) if maximum_mtime is not None else None)
        for media_id, count, maximum_mtime in source_rows
    }
    return MediaPageResponse(
        items=[
            _list_item(
                records_by_id[media_id],
                source_facts.get(media_id, (0, None)),
            )
            for media_id in media_ids
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{media_id}/navigation", response_model=MediaNavigationResponse)
async def get_media_navigation(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    kind: str | None = None,
    media_status: str | None = Query(default=None, alias="status"),
    workflow_status: str | None = None,
    evaluation_state: str | None = None,
    trash: bool | None = None,
    source_root_id: UUID | None = None,
    checkpoint_reference_id: UUID | None = None,
    lora_reference_id: UUID | None = None,
    sort: MediaSort = "file_created_desc",
) -> MediaNavigationResponse:
    id_query = _media_id_query(
        kind=kind,
        media_status=media_status,
        workflow_status=workflow_status,
        evaluation_state=evaluation_state,
        trash=trash,
        source_root_id=source_root_id,
        checkpoint_reference_id=checkpoint_reference_id,
        lora_reference_id=lora_reference_id,
    )
    order = _media_order(sort)
    ranked = id_query.add_columns(
        func.row_number().over(order_by=order).label("position"),
        func.count().over().label("total"),
        func.lag(Media.id).over(order_by=order).label("previous_id"),
        func.lead(Media.id).over(order_by=order).label("next_id"),
    ).subquery()
    row = (
        await session.execute(
            select(
                ranked.c.position,
                ranked.c.total,
                ranked.c.previous_id,
                ranked.c.next_id,
            ).where(ranked.c.id == media_id)
        )
    ).one_or_none()
    if row is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_IN_VIEW",
            message="The media record is not part of this library view.",
        )
    position = int(row.position)
    previous_id = row.previous_id
    next_id = row.next_id
    return MediaNavigationResponse(
        media_id=media_id,
        position=position,
        total=int(row.total),
        previous_id=previous_id,
        previous_position=position - 1 if previous_id is not None else None,
        next_id=next_id,
        next_position=position + 1 if next_id is not None else None,
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


def _list_item(
    media: Media,
    source_facts: tuple[int, int | None],
) -> MediaListItemResponse:
    asset = media.asset
    source_count, source_mtime_ns = source_facts
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
        file_created_at=_file_created_at(source_mtime_ns, media.created_at),
        created_at=media.created_at,
        preview_url=f"/api/v1/media/{media.id}/preview",
    )


def _media_id_query(
    *,
    kind: str | None,
    media_status: str | None,
    workflow_status: str | None,
    evaluation_state: str | None,
    trash: bool | None,
    source_root_id: UUID | None,
    checkpoint_reference_id: UUID | None,
    lora_reference_id: UUID | None,
) -> Select[tuple[UUID]]:
    filters: list[ColumnElement[bool]] = []
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
    if source_root_id is not None:
        filters.append(
            select(SourceOccurrence.id)
            .where(
                SourceOccurrence.media_id == Media.id,
                SourceOccurrence.source_root_id == source_root_id,
                SourceOccurrence.superseded_at.is_(None),
            )
            .exists()
        )
    if checkpoint_reference_id is not None:
        filters.append(
            _model_usage_exists(
                checkpoint_reference_id,
                observation_type="checkpoint_reference",
            )
        )
    if lora_reference_id is not None:
        filters.append(
            _model_usage_exists(
                lora_reference_id,
                observation_type="lora_reference",
            )
        )
    return select(Media.id).join(MediaAsset, MediaAsset.media_id == Media.id).where(*filters)


def _model_usage_exists(
    reference_id: UUID,
    *,
    observation_type: str,
) -> ColumnElement[bool]:
    return (
        select(ModelUsage.id)
        .join(WorkflowSnapshot, WorkflowSnapshot.id == ModelUsage.snapshot_id)
        .where(
            WorkflowSnapshot.media_id == Media.id,
            ModelUsage.model_reference_id == reference_id,
            ModelUsage.observation_type == observation_type,
        )
        .exists()
    )


def _media_order(sort: MediaSort) -> tuple[ColumnElement[Any], ...]:
    if sort == "file_created_asc":
        file_time = _file_time_ns()
        return (
            file_time.asc(),
            Media.created_at.asc(),
            Media.id.asc(),
        )
    if sort == "imported_desc":
        return (Media.created_at.desc(), Media.id.desc())
    if sort == "imported_asc":
        return (Media.created_at.asc(), Media.id.asc())
    if sort == "filename_asc":
        return (
            func.lower(MediaAsset.original_filename).asc(),
            Media.created_at.desc(),
            Media.id.desc(),
        )
    if sort == "filename_desc":
        return (
            func.lower(MediaAsset.original_filename).desc(),
            Media.created_at.desc(),
            Media.id.desc(),
        )
    if sort == "size_desc":
        return (MediaAsset.byte_size.desc(), Media.created_at.desc(), Media.id.desc())
    if sort == "size_asc":
        return (MediaAsset.byte_size.asc(), Media.created_at.desc(), Media.id.desc())
    file_time = _file_time_ns()
    return (
        file_time.desc(),
        Media.created_at.desc(),
        Media.id.desc(),
    )


def _source_mtime_ns() -> Any:
    return (
        select(func.max(SourceOccurrence.mtime_ns))
        .where(
            SourceOccurrence.media_id == Media.id,
            SourceOccurrence.superseded_at.is_(None),
        )
        .correlate(Media)
        .scalar_subquery()
    )


def _file_time_ns() -> Any:
    imported_at_ns = extract("epoch", Media.created_at) * 1_000_000_000
    return func.coalesce(_source_mtime_ns(), imported_at_ns)


def _file_created_at(source_mtime_ns: int | None, fallback: datetime) -> datetime:
    if source_mtime_ns is None:
        return fallback
    try:
        return datetime.fromtimestamp(source_mtime_ns / 1_000_000_000, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return fallback


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
