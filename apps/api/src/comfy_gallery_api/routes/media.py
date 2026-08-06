import random
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import ColumnElement, Select

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_filters import (
    MEDIA_SEARCH_QUERY_DESCRIPTION,
    MEDIA_SEARCH_QUERY_MAX_LENGTH,
    MEDIA_SHA256_QUERY_DESCRIPTION,
    MEDIA_SHA256_QUERY_LENGTH,
    MEDIA_SHA256_QUERY_PATTERN,
    media_keyword_filter,
    media_sha256_filter,
)
from comfy_gallery_api.media_schemas import (
    DerivativeResponse,
    MediaDetailResponse,
    MediaFavoriteResponse,
    MediaFavoriteUpdateRequest,
    MediaListItemResponse,
    MediaNavigationResponse,
    MediaPageResponse,
    MediaPlaybackPreferenceResponse,
    MediaPlaybackPreferenceUpdateRequest,
    MediaSpatialPreferenceResponse,
    MediaSpatialPreferenceUpdateRequest,
    MediaVariantResponse,
    SlideshowItemResponse,
    SlideshowPlaylistResponse,
    SourceOccurrenceResponse,
)
from comfy_gallery_core.db.models import (
    CollectionItem,
    Evaluation,
    Media,
    MediaAsset,
    MediaCollection,
    MediaVariant,
    ModelUsage,
    SourceOccurrence,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path
from comfy_gallery_core.registry.aliases import reference_identity_ids

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
ReferenceMatch = Literal["any", "all"]


@router.get("", response_model=MediaPageResponse)
async def list_media(
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = Query(
        default=None,
        max_length=MEDIA_SEARCH_QUERY_MAX_LENGTH,
        description=MEDIA_SEARCH_QUERY_DESCRIPTION,
    ),
    sha256: str | None = Query(
        default=None,
        min_length=MEDIA_SHA256_QUERY_LENGTH,
        max_length=MEDIA_SHA256_QUERY_LENGTH,
        pattern=MEDIA_SHA256_QUERY_PATTERN,
        description=MEDIA_SHA256_QUERY_DESCRIPTION,
    ),
    kind: str | None = None,
    media_status: str | None = Query(default=None, alias="status"),
    workflow_status: str | None = None,
    evaluation_state: str | None = None,
    trash: bool | None = None,
    prefer_spatial_playback: bool | None = None,
    spatial_view_preferred: bool | None = None,
    spatial_available: bool | None = None,
    favorite: bool | None = None,
    source_root_id: UUID | None = None,
    checkpoint_reference_id: Annotated[list[UUID] | None, Query()] = None,
    checkpoint_reference_match: ReferenceMatch = "any",
    lora_reference_id: Annotated[list[UUID] | None, Query()] = None,
    lora_reference_match: ReferenceMatch = "any",
    sort: MediaSort = "file_created_desc",
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> MediaPageResponse:
    preference_filter = _resolve_preference_filter(
        canonical=prefer_spatial_playback,
        legacy=spatial_view_preferred,
    )
    id_query = _media_id_query(
        q=q,
        sha256=sha256,
        kind=kind,
        media_status=media_status,
        workflow_status=workflow_status,
        evaluation_state=evaluation_state,
        trash=trash,
        prefer_spatial_playback=preference_filter,
        spatial_available=spatial_available,
        favorite=favorite,
        source_root_id=source_root_id,
        collection_id=None,
        checkpoint_reference_ids=checkpoint_reference_id or [],
        checkpoint_reference_match=checkpoint_reference_match,
        lora_reference_ids=lora_reference_id or [],
        lora_reference_match=lora_reference_match,
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


@router.get("/slideshow", response_model=SlideshowPlaylistResponse)
async def get_slideshow_playlist(
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = Query(
        default=None,
        max_length=MEDIA_SEARCH_QUERY_MAX_LENGTH,
        description=MEDIA_SEARCH_QUERY_DESCRIPTION,
    ),
    sha256: str | None = Query(
        default=None,
        min_length=MEDIA_SHA256_QUERY_LENGTH,
        max_length=MEDIA_SHA256_QUERY_LENGTH,
        pattern=MEDIA_SHA256_QUERY_PATTERN,
        description=MEDIA_SHA256_QUERY_DESCRIPTION,
    ),
    kind: str | None = None,
    media_status: str | None = Query(default=None, alias="status"),
    workflow_status: str | None = None,
    evaluation_state: str | None = None,
    trash: bool | None = None,
    prefer_spatial_playback: bool | None = None,
    spatial_view_preferred: bool | None = None,
    spatial_available: bool | None = None,
    favorite: bool | None = None,
    source_root_id: UUID | None = None,
    collection_id: UUID | None = None,
    checkpoint_reference_id: Annotated[list[UUID] | None, Query()] = None,
    checkpoint_reference_match: ReferenceMatch = "any",
    lora_reference_id: Annotated[list[UUID] | None, Query()] = None,
    lora_reference_match: ReferenceMatch = "any",
    sort: MediaSort = "file_created_desc",
    shuffle: bool = False,
    random_seed: int | None = Query(default=None, ge=0, le=2_147_483_647),
    limit: int = Query(default=2000, ge=1, le=2000),
) -> SlideshowPlaylistResponse:
    if collection_id is not None and await session.get(MediaCollection, collection_id) is None:
        raise ApiError(
            status_code=404,
            code="COLLECTION_NOT_FOUND",
            message="The collection was not found.",
        )
    preference_filter = _resolve_preference_filter(
        canonical=prefer_spatial_playback,
        legacy=spatial_view_preferred,
    )
    id_query = _media_id_query(
        q=q,
        sha256=sha256,
        kind=kind,
        media_status=media_status,
        workflow_status=workflow_status,
        evaluation_state=evaluation_state,
        trash=trash,
        prefer_spatial_playback=preference_filter,
        spatial_available=spatial_available,
        favorite=favorite,
        source_root_id=source_root_id,
        collection_id=collection_id,
        checkpoint_reference_ids=checkpoint_reference_id or [],
        checkpoint_reference_match=checkpoint_reference_match,
        lora_reference_ids=lora_reference_id or [],
        lora_reference_match=lora_reference_match,
    )
    total = int(await session.scalar(select(func.count()).select_from(id_query.subquery())) or 0)
    media_ids = list(await session.scalars(id_query.order_by(*_media_order(sort)).limit(limit)))
    resolved_seed: int | None = None
    if shuffle:
        resolved_seed = random_seed if random_seed is not None else secrets.randbelow(2_147_483_648)
        random.Random(resolved_seed).shuffle(media_ids)
    if not media_ids:
        return SlideshowPlaylistResponse(
            items=[],
            total=total,
            limit=limit,
            truncated=total > limit,
            shuffle=shuffle,
            random_seed=resolved_seed,
        )
    records = list(
        await session.scalars(
            select(Media).options(selectinload(Media.asset)).where(Media.id.in_(media_ids))
        )
    )
    records_by_id = {record.id: record for record in records}
    return SlideshowPlaylistResponse(
        items=[_slideshow_item(records_by_id[media_id]) for media_id in media_ids],
        total=total,
        limit=limit,
        truncated=total > len(media_ids),
        shuffle=shuffle,
        random_seed=resolved_seed,
    )


@router.get("/{media_id}/navigation", response_model=MediaNavigationResponse)
async def get_media_navigation(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = Query(
        default=None,
        max_length=MEDIA_SEARCH_QUERY_MAX_LENGTH,
        description=MEDIA_SEARCH_QUERY_DESCRIPTION,
    ),
    sha256: str | None = Query(
        default=None,
        min_length=MEDIA_SHA256_QUERY_LENGTH,
        max_length=MEDIA_SHA256_QUERY_LENGTH,
        pattern=MEDIA_SHA256_QUERY_PATTERN,
        description=MEDIA_SHA256_QUERY_DESCRIPTION,
    ),
    kind: str | None = None,
    media_status: str | None = Query(default=None, alias="status"),
    workflow_status: str | None = None,
    evaluation_state: str | None = None,
    trash: bool | None = None,
    prefer_spatial_playback: bool | None = None,
    spatial_view_preferred: bool | None = None,
    spatial_available: bool | None = None,
    favorite: bool | None = None,
    source_root_id: UUID | None = None,
    checkpoint_reference_id: Annotated[list[UUID] | None, Query()] = None,
    checkpoint_reference_match: ReferenceMatch = "any",
    lora_reference_id: Annotated[list[UUID] | None, Query()] = None,
    lora_reference_match: ReferenceMatch = "any",
    sort: MediaSort = "file_created_desc",
) -> MediaNavigationResponse:
    preference_filter = _resolve_preference_filter(
        canonical=prefer_spatial_playback,
        legacy=spatial_view_preferred,
    )
    id_query = _media_id_query(
        q=q,
        sha256=sha256,
        kind=kind,
        media_status=media_status,
        workflow_status=workflow_status,
        evaluation_state=evaluation_state,
        trash=trash,
        prefer_spatial_playback=preference_filter,
        spatial_available=spatial_available,
        favorite=favorite,
        source_root_id=source_root_id,
        collection_id=None,
        checkpoint_reference_ids=checkpoint_reference_id or [],
        checkpoint_reference_match=checkpoint_reference_match,
        lora_reference_ids=lora_reference_id or [],
        lora_reference_match=lora_reference_match,
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
    source_mtime_ns = max(
        (source.mtime_ns for source in media.source_occurrences if source.superseded_at is None),
        default=None,
    )
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
        file_created_at=_file_created_at(source_mtime_ns, media.created_at),
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
        spatial_available=media.spatial_available,
        prefer_spatial_playback=media.prefer_spatial_playback,
        spatial_view_preferred=media.spatial_view_preferred,
        favorite=media.favorite,
        derivatives=[DerivativeResponse.model_validate(item) for item in media.derivatives],
        variants=[_variant_response(item) for item in media.variants if _is_public_variant(item)],
        sources=[
            SourceOccurrenceResponse.model_validate(item) for item in media.source_occurrences
        ],
    )


@router.put(
    "/{media_id}/playback-preference",
    response_model=MediaPlaybackPreferenceResponse,
)
async def update_media_playback_preference(
    media_id: UUID,
    request: MediaPlaybackPreferenceUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> MediaPlaybackPreferenceResponse:
    media = await _get_media_record(session, media_id)
    media.prefer_spatial_playback = request.prefer_spatial_playback
    await session.commit()
    await session.refresh(media)
    return MediaPlaybackPreferenceResponse(
        media_id=media.id,
        prefer_spatial_playback=media.prefer_spatial_playback,
        spatial_view_preferred=media.prefer_spatial_playback,
        updated_at=media.updated_at,
    )


@router.put(
    "/{media_id}/spatial-preference",
    response_model=MediaSpatialPreferenceResponse,
)
async def update_media_spatial_preference(
    media_id: UUID,
    request: MediaSpatialPreferenceUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> MediaSpatialPreferenceResponse:
    media = await _get_media_record(session, media_id)
    media.prefer_spatial_playback = request.spatial_view_preferred
    await session.commit()
    await session.refresh(media)
    return MediaSpatialPreferenceResponse(
        media_id=media.id,
        prefer_spatial_playback=media.prefer_spatial_playback,
        spatial_view_preferred=media.prefer_spatial_playback,
        updated_at=media.updated_at,
    )


@router.put(
    "/{media_id}/favorite",
    response_model=MediaFavoriteResponse,
)
async def update_media_favorite(
    media_id: UUID,
    request: MediaFavoriteUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> MediaFavoriteResponse:
    media = await session.get(Media, media_id)
    if media is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    media.favorite = request.favorite
    await session.commit()
    await session.refresh(media)
    return MediaFavoriteResponse(
        media_id=media.id,
        favorite=media.favorite,
        updated_at=media.updated_at,
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
            selectinload(Media.variants),
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


async def _get_media_record(session: DbSessionDep, media_id: UUID) -> Media:
    media = await session.get(Media, media_id)
    if media is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    return media


def _resolve_preference_filter(
    *,
    canonical: bool | None,
    legacy: bool | None,
) -> bool | None:
    if canonical is not None and legacy is not None and canonical != legacy:
        raise ApiError(
            status_code=422,
            code="SPATIAL_PREFERENCE_FILTER_CONFLICT",
            message=(
                "prefer_spatial_playback and spatial_view_preferred cannot specify "
                "different values."
            ),
        )
    return canonical if canonical is not None else legacy


def _is_public_variant(variant: MediaVariant) -> bool:
    return (
        variant.status == "ready"
        and variant.is_active
        and variant.mime_type is not None
        and variant.byte_size is not None
        and variant.ready_at is not None
    )


def _variant_response(variant: MediaVariant) -> MediaVariantResponse:
    if variant.mime_type is None or variant.byte_size is None or variant.ready_at is None:
        raise ValueError("An active ready variant is missing required file facts.")
    return MediaVariantResponse(
        id=variant.id,
        role=variant.role,
        status=variant.status,
        mime_type=variant.mime_type,
        byte_size=variant.byte_size,
        width=variant.width,
        height=variant.height,
        duration_seconds=variant.duration_seconds,
        frame_rate=variant.frame_rate,
        container=variant.container,
        video_codec=variant.video_codec,
        audio_codec=variant.audio_codec,
        converter_name=variant.converter_name,
        converter_version=variant.converter_version,
        ready_at=variant.ready_at,
        content_url=f"/api/v1/media/{variant.media_id}/variants/{variant.id}/content",
    )


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
        spatial_available=media.spatial_available,
        prefer_spatial_playback=media.prefer_spatial_playback,
        spatial_view_preferred=media.spatial_view_preferred,
        favorite=media.favorite,
        file_created_at=_file_created_at(source_mtime_ns, media.created_at),
        created_at=media.created_at,
        preview_url=f"/api/v1/media/{media.id}/preview",
    )


def _slideshow_item(media: Media) -> SlideshowItemResponse:
    return SlideshowItemResponse(
        id=media.id,
        kind=media.kind,
        status=media.status,
        original_filename=media.asset.original_filename,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        preview_url=f"/api/v1/media/{media.id}/preview",
        playback_url=f"/api/v1/media/{media.id}/playback",
    )


def _media_id_query(
    *,
    q: str | None,
    sha256: str | None,
    kind: str | None,
    media_status: str | None,
    workflow_status: str | None,
    evaluation_state: str | None,
    trash: bool | None,
    prefer_spatial_playback: bool | None,
    spatial_available: bool | None,
    favorite: bool | None,
    source_root_id: UUID | None,
    collection_id: UUID | None,
    checkpoint_reference_ids: list[UUID],
    checkpoint_reference_match: ReferenceMatch,
    lora_reference_ids: list[UUID],
    lora_reference_match: ReferenceMatch,
) -> Select[tuple[UUID]]:
    filters: list[ColumnElement[bool]] = []
    keyword_filter = media_keyword_filter(q)
    if keyword_filter is not None:
        filters.append(keyword_filter)
    hash_filter = media_sha256_filter(sha256)
    if hash_filter is not None:
        filters.append(hash_filter)
    if kind:
        filters.append(Media.kind == kind)
    if media_status:
        filters.append(Media.status == media_status)
    if prefer_spatial_playback is not None:
        filters.append(Media.prefer_spatial_playback.is_(prefer_spatial_playback))
    if spatial_available is not None:
        filters.append(Media.spatial_available.is_(spatial_available))
    if favorite is not None:
        filters.append(Media.favorite.is_(favorite))
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
    if collection_id is not None:
        filters.append(
            select(CollectionItem.media_id)
            .where(
                CollectionItem.media_id == Media.id,
                CollectionItem.collection_id == collection_id,
            )
            .exists()
        )
    checkpoint_filter = _model_usage_filter(
        checkpoint_reference_ids,
        match=checkpoint_reference_match,
        observation_type="checkpoint_reference",
    )
    if checkpoint_filter is not None:
        filters.append(checkpoint_filter)
    lora_filter = _model_usage_filter(
        lora_reference_ids,
        match=lora_reference_match,
        observation_type="lora_reference",
    )
    if lora_filter is not None:
        filters.append(lora_filter)
    return select(Media.id).join(MediaAsset, MediaAsset.media_id == Media.id).where(*filters)


def _model_usage_filter(
    reference_ids: list[UUID],
    *,
    match: ReferenceMatch,
    observation_type: str,
) -> ColumnElement[bool] | None:
    unique_ids = list(dict.fromkeys(reference_ids))
    if not unique_ids:
        return None
    clauses = [
        _model_usage_exists(
            reference_id,
            observation_type=observation_type,
        )
        for reference_id in unique_ids
    ]
    return and_(*clauses) if match == "all" else or_(*clauses)


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
            ModelUsage.model_reference_id.in_(reference_identity_ids(reference_id)),
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
