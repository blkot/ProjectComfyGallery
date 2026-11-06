from __future__ import annotations

from typing import Any, Literal
from typing import cast as typing_cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Select, and_, case, exists, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.sql.elements import ColumnElement

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    MediaNavigationResponse,
    SlideshowItemResponse,
    SlideshowPlaylistResponse,
)
from comfy_gallery_api.prompt_registry_schemas import (
    PromptRegistryCharacterLoraResponse,
    PromptRegistryEntryRequest,
    PromptRegistryEntryResponse,
    PromptRegistryHeatmapItemResponse,
    PromptRegistryHeatmapResponse,
    PromptRegistryImportRequest,
    PromptRegistryImportResponse,
    PromptRegistryLookupResponse,
    PromptRegistryMaterialization,
    PromptRegistryMediaResponse,
    PromptRegistryNeighborResponse,
    PromptRegistryPageResponse,
    PromptRegistryRandomResponse,
    PromptRegistryStatsResponse,
)
from comfy_gallery_core.db.models import (
    Evaluation,
    Media,
    MediaAsset,
    MediaPromptIndex,
    PromptRegistryEntry,
    WorkflowDisplayRecovery,
    WorkflowSnapshot,
)
from comfy_gallery_core.prompt_registry import (
    PromptIdentifier,
    normalize_prompt_source,
    parse_prompt_id,
)
from comfy_gallery_core.workflow.display_fields import (
    saved_fields,
)
from comfy_gallery_core.workflow.prompt_index import (
    load_profiles_by_scope,
    prompt_id_candidate,
    structural_prompt_id_candidate,
)

router = APIRouter(prefix="/api/v1/prompt-registry", tags=["prompt-registry"])
_PROMPT_REGISTRY_IMPORT_MAX_BYTES = 8 * 1024 * 1024


async def _enforce_import_body_size(request: Request) -> None:
    """Reject the actual encoded request body before importing any rows."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > _PROMPT_REGISTRY_IMPORT_MAX_BYTES:
                raise ApiError(
                    status_code=413,
                    code="PROMPT_REGISTRY_IMPORT_TOO_LARGE",
                    message="Prompt registry import payload must be 8 MB or smaller.",
                )
        except ValueError:
            pass
    if len(await request.body()) > _PROMPT_REGISTRY_IMPORT_MAX_BYTES:
        raise ApiError(
            status_code=413,
            code="PROMPT_REGISTRY_IMPORT_TOO_LARGE",
            message="Prompt registry import payload must be 8 MB or smaller.",
        )


@router.get("", response_model=PromptRegistryPageResponse)
async def list_prompt_registry_entries(
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = Query(default=None, max_length=256),
    source: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PromptRegistryPageResponse:
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                PromptRegistryEntry.source.ilike(pattern),
                PromptRegistryEntry.entry_index.ilike(pattern),
                PromptRegistryEntry.prompt.ilike(pattern),
            )
        )
    if source and source.strip():
        filters.append(PromptRegistryEntry.source_key == normalize_prompt_source(source))
    total = int(
        await session.scalar(select(func.count()).select_from(PromptRegistryEntry).where(*filters))
        or 0
    )
    entries = list(
        await session.scalars(
            select(PromptRegistryEntry)
            .where(*filters)
            .order_by(
                PromptRegistryEntry.source_key,
                func.length(PromptRegistryEntry.entry_index),
                PromptRegistryEntry.entry_index,
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return PromptRegistryPageResponse(
        items=[_entry_response(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sources", response_model=list[str])
async def list_prompt_registry_sources(
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = Query(default=None, max_length=256),
    limit: int = Query(default=24, ge=1, le=50),
) -> list[str]:
    """Return distinct source labels without searching prompt text."""

    filters = []
    if q and q.strip():
        filters.append(PromptRegistryEntry.source_key.startswith(normalize_prompt_source(q)))
    rows = await session.execute(
        select(
            PromptRegistryEntry.source_key,
            func.min(PromptRegistryEntry.source).label("source"),
        )
        .where(*filters)
        .group_by(PromptRegistryEntry.source_key)
        .order_by(PromptRegistryEntry.source_key)
        .limit(limit)
    )
    return [str(row.source) for row in rows]


@router.get("/character-loras", response_model=list[PromptRegistryCharacterLoraResponse])
async def list_prompt_registry_character_loras(
    _principal: PrincipalDep,
    session: DbSessionDep,
    q: str | None = None,
    limit: int = 50,
) -> list[PromptRegistryCharacterLoraResponse]:
    """Return character LoRA display values that have indexed media."""

    limit = max(1, min(limit, 200))
    filters = [
        MediaPromptIndex.character_lora.is_not(None),
        MediaPromptIndex.character_lora != "",
    ]
    if q and q.strip():
        filters.append(MediaPromptIndex.character_lora.ilike(f"%{q.strip()}%"))
    name = func.min(MediaPromptIndex.character_lora).label("name")
    media_count = func.count().label("media_count")
    rows = await session.execute(
        select(name, media_count)
        .select_from(MediaPromptIndex)
        .where(*filters)
        .group_by(func.lower(MediaPromptIndex.character_lora))
        .order_by(media_count.desc(), name.asc())
        .limit(limit)
    )
    return [
        PromptRegistryCharacterLoraResponse(name=str(row.name), media_count=int(row.media_count))
        for row in rows
    ]


@router.get("/heatmap", response_model=PromptRegistryHeatmapResponse)
async def prompt_registry_heatmap(
    _principal: PrincipalDep,
    session: DbSessionDep,
    source: str | None = Query(default=None, max_length=256),
    character_lora: str | None = None,
    include_not_faved: bool = False,
    include_trash: bool = False,
    limit: int = Query(default=20_000, ge=1, le=20_000),
    offset: int = Query(default=0, ge=0),
) -> PromptRegistryHeatmapResponse:
    filters = _source_filters(source)
    character_filter = (
        [func.lower(MediaPromptIndex.character_lora) == character_lora.strip().casefold()]
        if character_lora and character_lora.strip()
        else []
    )
    media_counts = (
        select(
            MediaPromptIndex.source_key.label("source_key"),
            MediaPromptIndex.index_key.label("index_key"),
            func.count(MediaPromptIndex.media_id).label("media_count"),
        )
        .join(Media, Media.id == MediaPromptIndex.media_id)
        .where(
            MediaPromptIndex.source_key.is_not(None),
            MediaPromptIndex.index_key.is_not(None),
            _heatmap_media_scope(
                include_not_faved=include_not_faved,
                include_trash=include_trash,
            ),
            *character_filter,
        )
        .group_by(MediaPromptIndex.source_key, MediaPromptIndex.index_key)
        .subquery("prompt_registry_media_counts")
    )
    join_condition = and_(
        media_counts.c.source_key == PromptRegistryEntry.source_key,
        media_counts.c.index_key == PromptRegistryEntry.entry_index_key,
    )
    total = int(
        await session.scalar(select(func.count()).select_from(PromptRegistryEntry).where(*filters))
        or 0
    )
    max_media_count = int(
        await session.scalar(
            select(
                func.coalesce(
                    func.max(func.coalesce(media_counts.c.media_count, 0)),
                    0,
                )
            )
            .select_from(PromptRegistryEntry)
            .outerjoin(media_counts, join_condition)
            .where(*filters)
        )
        or 0
    )
    rows = list(
        (
            await session.execute(
                select(
                    PromptRegistryEntry,
                    func.coalesce(media_counts.c.media_count, 0).label("media_count"),
                )
                .outerjoin(media_counts, join_condition)
                .where(*filters)
                .order_by(
                    PromptRegistryEntry.source_key,
                    func.length(PromptRegistryEntry.entry_index_key),
                    PromptRegistryEntry.entry_index_key,
                    PromptRegistryEntry.entry_index,
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
    )
    return PromptRegistryHeatmapResponse(
        items=[
            PromptRegistryHeatmapItemResponse(
                prompt_id=PromptIdentifier(source=entry.source, index=entry.entry_index).display,
                source=entry.source,
                index=entry.entry_index,
                media_count=int(media_count),
            )
            for entry, media_count in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
        max_media_count=max_media_count,
    )


@router.get("/random", response_model=PromptRegistryRandomResponse)
async def random_prompt_registry_entry(
    _principal: PrincipalDep,
    session: DbSessionDep,
    source: str | None = Query(default=None, max_length=256),
    character_lora: str | None = None,
    materialization: PromptRegistryMaterialization = "any",
) -> PromptRegistryRandomResponse:
    character = _normalized_character_lora(character_lora)
    filters = _source_filters(source)
    materialized_expression = _favorite_media_exists_expression(character)
    if materialization == "materialized":
        filters.append(materialized_expression)
    elif materialization == "unmaterialized":
        filters.append(~materialized_expression)

    entry = await session.scalar(
        select(PromptRegistryEntry).where(*filters).order_by(func.random()).limit(1)
    )
    if entry is None:
        raise ApiError(
            status_code=404,
            code="PROMPT_REGISTRY_RANDOM_NOT_FOUND",
            message="No prompt matches the requested filters.",
        )

    media_count = await _favorite_media_count(session, entry, character)
    entry_response = _entry_response(entry, media_count=media_count)
    return PromptRegistryRandomResponse(
        **entry_response.model_dump(),
        prompt_id=PromptIdentifier(source=entry.source, index=entry.entry_index).display,
        materialization="materialized" if media_count else "unmaterialized",
    )


@router.get("/stats", response_model=PromptRegistryStatsResponse)
async def prompt_registry_stats(
    _principal: PrincipalDep,
    session: DbSessionDep,
    source: str | None = Query(default=None, max_length=256),
    character_lora: str | None = None,
) -> PromptRegistryStatsResponse:
    character = _normalized_character_lora(character_lora)
    filters = _source_filters(source)
    registered_count = int(
        await session.scalar(select(func.count()).select_from(PromptRegistryEntry).where(*filters))
        or 0
    )
    materialized_count = int(
        await session.scalar(
            select(func.count())
            .select_from(PromptRegistryEntry)
            .where(*filters, _favorite_media_exists_expression(character))
        )
        or 0
    )
    source_count = int(
        await session.scalar(
            select(func.count(func.distinct(PromptRegistryEntry.source_key)))
            .select_from(PromptRegistryEntry)
            .where(*filters)
        )
        or 0
    )
    return PromptRegistryStatsResponse(
        source=_normalized_source(source) if source is not None else None,
        source_count=source_count,
        registered_count=registered_count,
        materialized_count=materialized_count,
        unmaterialized_count=registered_count - materialized_count,
    )


@router.get("/neighbor", response_model=PromptRegistryNeighborResponse)
async def prompt_registry_neighbor(
    _principal: PrincipalDep,
    session: DbSessionDep,
    source: str = Query(min_length=1, max_length=256),
    index: str = Query(min_length=1, max_length=128, pattern=r"^\d+$"),
    direction: Literal["previous", "next"] = Query(...),
) -> PromptRegistryNeighborResponse:
    identifier = PromptIdentifier(source=_normalized_source(source), index=index)
    index_length = len(identifier.index_key)
    indexed_length = func.length(PromptRegistryEntry.entry_index_key)
    same_source = PromptRegistryEntry.source_key == identifier.source_key
    if direction == "previous":
        position_filter = or_(
            indexed_length < index_length,
            and_(
                indexed_length == index_length,
                PromptRegistryEntry.entry_index_key < identifier.index_key,
            ),
        )
        ordering = (
            indexed_length.desc(),
            PromptRegistryEntry.entry_index_key.desc(),
            PromptRegistryEntry.entry_index.desc(),
        )
    else:
        position_filter = or_(
            indexed_length > index_length,
            and_(
                indexed_length == index_length,
                PromptRegistryEntry.entry_index_key > identifier.index_key,
            ),
        )
        ordering = (
            indexed_length.asc(),
            PromptRegistryEntry.entry_index_key.asc(),
            PromptRegistryEntry.entry_index.asc(),
        )

    entry = await session.scalar(
        select(PromptRegistryEntry).where(same_source, position_filter).order_by(*ordering).limit(1)
    )
    if entry is None:
        raise ApiError(
            status_code=404,
            code="PROMPT_REGISTRY_NEIGHBOR_NOT_FOUND",
            message="No registered neighbor prompt was found.",
            details={
                "source": identifier.source,
                "index": identifier.index,
                "direction": direction,
            },
        )

    return PromptRegistryNeighborResponse(
        direction=direction,
        entry=_entry_response(
            entry,
            media_count=await _favorite_media_count(session, entry),
        ),
    )


@router.get("/lookup", response_model=PromptRegistryLookupResponse)
async def lookup_prompt_registry_entry(
    _principal: PrincipalDep,
    session: DbSessionDep,
    prompt_id: str = Query(min_length=1, max_length=512),
    character_lora: str | None = None,
    group_by_character: bool = False,
    preferred_character_lora: str | None = None,
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PromptRegistryLookupResponse:
    identifier = _usage_identifier(prompt_id)
    entry = await _find_entry(session, identifier)
    query = await _usage_query(session, identifier, character_lora)
    total, media = await _usage_page(
        session,
        query,
        limit=limit,
        offset=offset,
        group_by_character=group_by_character,
        preferred_character_lora=preferred_character_lora,
    )
    display_identifier = (
        PromptIdentifier(source=entry.source, index=entry.entry_index)
        if entry is not None
        else identifier
    )
    trashed_ids = await _trashed_media_ids(session, [media.id for media, _asset in media])
    character_loras = await _character_loras_for_media(
        session, [media.id for media, _asset in media]
    )
    return PromptRegistryLookupResponse(
        prompt_id=display_identifier.display,
        source=display_identifier.source,
        index=display_identifier.index,
        entry=_entry_response(entry, media_count=total) if entry else None,
        media=[
            _media_response(
                row,
                is_trash=row[0].id in trashed_ids,
                character_lora=character_loras.get(row[0].id),
            )
            for row in media
        ],
        total_media=total,
        limit=limit,
        offset=offset,
    )


@router.get("/usage/navigation", response_model=MediaNavigationResponse)
async def prompt_usage_navigation(
    _principal: PrincipalDep,
    session: DbSessionDep,
    media_id: UUID,
    prompt_id: str = Query(min_length=1, max_length=512),
    character_lora: str | None = None,
    preferred_character_lora: str | None = None,
) -> MediaNavigationResponse:
    """Navigate the same grouped scope as lookup, not the complete Library."""

    query = await _usage_query(session, _usage_identifier(prompt_id), character_lora)
    return await _usage_navigation(session, query, media_id, preferred_character_lora)


@router.get("/usage/slideshow", response_model=SlideshowPlaylistResponse)
async def prompt_usage_slideshow(
    _principal: PrincipalDep,
    session: DbSessionDep,
    prompt_id: str = Query(min_length=1, max_length=512),
    character_lora: str | None = None,
    preferred_character_lora: str | None = None,
    start_media_id: UUID | None = None,
    limit: int = Query(default=2_000, ge=1, le=2_000),
) -> SlideshowPlaylistResponse:
    query = await _usage_query(session, _usage_identifier(prompt_id), character_lora)
    if start_media_id is not None:
        order = _usage_order(True, preferred_character_lora)
        ranked = query.with_only_columns(
            Media.id,
            func.row_number().over(order_by=order).label("position"),
            func.count().over().label("total"),
        ).cte("ranked_prompt_usage")
        start_position = (
            select(ranked.c.position).where(ranked.c.id == start_media_id).scalar_subquery()
        )
        # Keep start resolution and page selection in one database snapshot.
        window = (
            await session.execute(
                select(Media, MediaAsset, ranked.c.total)
                .join(MediaAsset, MediaAsset.media_id == Media.id)
                .join(ranked, ranked.c.id == Media.id)
                .where(ranked.c.position >= start_position)
                .order_by(ranked.c.position)
                .limit(limit)
            )
        ).all()
        if not window:
            raise ApiError(
                status_code=404,
                code="MEDIA_NOT_IN_VIEW",
                message="The starting media is not part of this prompt usage view.",
            )
        total = int(window[0][2])
        rows = [(media, asset) for media, asset, _total in window]
    else:
        total, rows = await _usage_page(
            session,
            query,
            limit=limit,
            offset=0,
            group_by_character=True,
            preferred_character_lora=preferred_character_lora,
        )
    return SlideshowPlaylistResponse(
        items=[
            SlideshowItemResponse(
                id=media.id,
                kind=media.kind,
                status=media.status,
                original_filename=asset.original_filename,
                width=media.width,
                height=media.height,
                duration_seconds=media.duration_seconds,
                preview_url=f"/api/v1/media/{media.id}/preview",
                playback_url=f"/api/v1/media/{media.id}/playback",
            )
            for media, asset in rows
        ],
        total=total,
        limit=limit,
        truncated=total > len(rows),
        shuffle=False,
        random_seed=None,
    )


@router.get("/{entry_id}", response_model=PromptRegistryLookupResponse)
async def get_prompt_registry_entry(
    entry_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    character_lora: str | None = None,
    group_by_character: bool = False,
    preferred_character_lora: str | None = None,
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PromptRegistryLookupResponse:
    entry = await session.get(PromptRegistryEntry, entry_id)
    if entry is None:
        raise ApiError(
            status_code=404,
            code="PROMPT_REGISTRY_ENTRY_NOT_FOUND",
            message="The prompt registry entry was not found.",
        )
    identifier = PromptIdentifier(source=entry.source, index=entry.entry_index)
    query = await _usage_query(session, identifier, character_lora)
    total, media = await _usage_page(
        session,
        query,
        limit=limit,
        offset=offset,
        group_by_character=group_by_character,
        preferred_character_lora=preferred_character_lora,
    )
    trashed_ids = await _trashed_media_ids(session, [media.id for media, _asset in media])
    character_loras = await _character_loras_for_media(
        session, [media.id for media, _asset in media]
    )
    return PromptRegistryLookupResponse(
        prompt_id=identifier.display,
        source=identifier.source,
        index=identifier.index,
        entry=_entry_response(entry, media_count=total),
        media=[
            _media_response(
                row,
                is_trash=row[0].id in trashed_ids,
                character_lora=character_loras.get(row[0].id),
            )
            for row in media
        ],
        total_media=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/import",
    response_model=PromptRegistryImportResponse,
    dependencies=[Depends(_enforce_import_body_size)],
)
async def import_prompt_registry_entries(
    request: PromptRegistryImportRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> PromptRegistryImportResponse:
    rows: list[dict[str, object]] = []
    keys: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in request.entries:
        source = _normalized_source(item.source)
        entry_index = item.index.strip()
        source_key = normalize_prompt_source(source)
        key = (source_key, entry_index)
        if key in seen:
            raise ApiError(
                status_code=422,
                code="DUPLICATE_PROMPT_REGISTRY_KEY",
                message="A batch cannot contain duplicate source and index keys.",
                details={"source": source, "index": entry_index},
            )
        seen.add(key)
        keys.append(key)
        rows.append(
            {
                "source": source,
                "source_key": source_key,
                "entry_index": entry_index,
                "entry_index_key": PromptIdentifier(
                    source=source,
                    index=entry_index,
                ).index_key,
                "prompt": item.prompt,
                "negative_prompt": item.negative_prompt,
                "metadata": item.metadata,
                "origin": item.origin,
            }
        )

    existing_result = await session.execute(
        select(PromptRegistryEntry.source_key, PromptRegistryEntry.entry_index).where(
            tuple_(PromptRegistryEntry.source_key, PromptRegistryEntry.entry_index).in_(keys)
        )
    )
    existing_keys = {(source_key, entry_index) for source_key, entry_index in existing_result}
    statement = _prompt_registry_upsert_statement(session, rows)
    await session.execute(statement)
    await session.commit()

    imported_predicates = tuple_(
        PromptRegistryEntry.source_key,
        PromptRegistryEntry.entry_index,
    ).in_(keys)
    persisted_entries = list(
        await session.scalars(select(PromptRegistryEntry).where(imported_predicates))
    )
    persisted_by_key = {(entry.source_key, entry.entry_index): entry for entry in persisted_entries}
    created_count = len(keys) - len(existing_keys)
    updated_count = len(keys) - created_count
    return PromptRegistryImportResponse(
        created_count=created_count,
        updated_count=updated_count,
        entries=[_entry_response(persisted_by_key[entry_key]) for entry_key in keys],
    )


@router.post("", response_model=PromptRegistryEntryResponse, status_code=201)
async def create_prompt_registry_entry(
    request: PromptRegistryEntryRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> PromptRegistryEntryResponse:
    source = _normalized_source(request.source)
    entry_index = request.index.strip()
    existing = await _find_entry(
        session,
        PromptIdentifier(source=source, index=entry_index),
    )
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="PROMPT_REGISTRY_ENTRY_EXISTS",
            message="A prompt registry entry already exists for this source and index.",
        )
    entry = PromptRegistryEntry(
        source=source,
        source_key=normalize_prompt_source(source),
        entry_index=entry_index,
        entry_index_key=PromptIdentifier(source=source, index=entry_index).index_key,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        entry_metadata=request.metadata,
        origin=request.origin,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return _entry_response(entry)


@router.put("/{entry_id}", response_model=PromptRegistryEntryResponse)
async def update_prompt_registry_entry(
    entry_id: UUID,
    request: PromptRegistryEntryRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> PromptRegistryEntryResponse:
    entry = await session.get(PromptRegistryEntry, entry_id)
    if entry is None:
        raise ApiError(
            status_code=404,
            code="PROMPT_REGISTRY_ENTRY_NOT_FOUND",
            message="The prompt registry entry was not found.",
        )
    source = _normalized_source(request.source)
    entry_index = request.index.strip()
    conflict = await _find_entry(
        session,
        PromptIdentifier(source=source, index=entry_index),
    )
    if conflict is not None and conflict.id != entry.id:
        raise ApiError(
            status_code=409,
            code="PROMPT_REGISTRY_ENTRY_EXISTS",
            message="A prompt registry entry already exists for this source and index.",
        )
    entry.source = source
    entry.source_key = normalize_prompt_source(source)
    entry.entry_index = entry_index
    entry.entry_index_key = PromptIdentifier(source=source, index=entry_index).index_key
    entry.prompt = request.prompt
    entry.negative_prompt = request.negative_prompt
    entry.entry_metadata = request.metadata
    entry.origin = request.origin
    await session.commit()
    await session.refresh(entry)
    return _entry_response(entry)


def _normalized_source(source: str) -> str:
    normalized = " ".join(source.split())
    if not normalized:
        raise ApiError(
            status_code=422,
            code="PROMPT_SOURCE_INVALID",
            message="Prompt registry source cannot be empty.",
        )
    return normalized


def _source_filters(source: str | None) -> list[Any]:
    if source is None:
        return []
    normalized = _normalized_source(source)
    return [PromptRegistryEntry.source_key == normalize_prompt_source(normalized)]


def _media_trash_expression() -> Any:
    """Trash lives on the base Evaluation of a media record, not on Media."""

    return exists(
        select(1)
        .select_from(Evaluation)
        .where(
            Evaluation.media_id == Media.id,
            Evaluation.evaluation_kind == "base",
            Evaluation.is_trash.is_(True),
        )
    )


def _normalized_character_lora(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    return normalized or None


def _favorite_media_exists_expression(character_lora: str | None = None) -> Any:
    """Report whether an entry produced at least one non-trashed favorite."""

    conditions = [
        MediaPromptIndex.source_key == PromptRegistryEntry.source_key,
        MediaPromptIndex.index_key == PromptRegistryEntry.entry_index_key,
        Media.favorite.is_(True),
        ~_media_trash_expression(),
    ]
    if character_lora is not None:
        conditions.append(func.lower(MediaPromptIndex.character_lora) == character_lora)
    return exists(
        select(1)
        .select_from(MediaPromptIndex)
        .join(Media, Media.id == MediaPromptIndex.media_id)
        .where(*conditions)
    ).correlate(PromptRegistryEntry)


async def _favorite_media_count(
    session: DbSessionDep,
    entry: PromptRegistryEntry,
    character_lora: str | None = None,
) -> int:
    conditions = [
        MediaPromptIndex.source_key == entry.source_key,
        MediaPromptIndex.index_key == entry.entry_index_key,
        Media.favorite.is_(True),
        ~_media_trash_expression(),
    ]
    if character_lora is not None:
        conditions.append(func.lower(MediaPromptIndex.character_lora) == character_lora)
    return int(
        await session.scalar(
            select(func.count())
            .select_from(MediaPromptIndex)
            .join(Media, Media.id == MediaPromptIndex.media_id)
            .where(*conditions)
        )
        or 0
    )


async def _trashed_media_ids(
    session: DbSessionDep,
    media_ids: list[UUID],
) -> set[UUID]:
    if not media_ids:
        return set()
    rows = await session.scalars(
        select(Media.id).where(
            Media.id.in_(media_ids),
            _media_trash_expression(),
        )
    )
    return set(rows)


async def _character_loras_for_media(
    session: DbSessionDep,
    media_ids: list[UUID],
) -> dict[UUID, str | None]:
    if not media_ids:
        return {}
    rows = await session.execute(
        select(MediaPromptIndex.media_id, MediaPromptIndex.character_lora).where(
            MediaPromptIndex.media_id.in_(media_ids)
        )
    )
    return {
        media_id: character_lora.strip() or None if isinstance(character_lora, str) else None
        for media_id, character_lora in rows
    }


def _heatmap_media_scope(*, include_not_faved: bool, include_trash: bool) -> Any:
    """Classify linked media into favorites, ordinary media, and Trash.

    Trash outranks Favorite: a trashed favorite is counted only when trash is
    requested, and a favorite counts only outside Trash. Ordinary media is
    excluded unless the caller asks for it.
    """

    trash_expression = _media_trash_expression()
    categories = [and_(~trash_expression, Media.favorite.is_(True))]
    if include_not_faved:
        categories.append(and_(~trash_expression, Media.favorite.is_(False)))
    if include_trash:
        categories.append(trash_expression)
    return or_(*categories)


async def _find_entry(
    session: DbSessionDep,
    identifier: PromptIdentifier,
) -> PromptRegistryEntry | None:
    exact = typing_cast(
        PromptRegistryEntry | None,
        await session.scalar(
            select(PromptRegistryEntry).where(
                PromptRegistryEntry.source_key == identifier.source_key,
                PromptRegistryEntry.entry_index == identifier.index,
            )
        ),
    )
    if exact is not None:
        return exact
    canonical = await session.scalar(
        select(PromptRegistryEntry)
        .where(
            PromptRegistryEntry.source_key == identifier.source_key,
            PromptRegistryEntry.entry_index_key == identifier.index_key,
        )
        .order_by(
            func.length(PromptRegistryEntry.entry_index),
            PromptRegistryEntry.entry_index,
        )
        .limit(1)
    )
    return canonical


def _prompt_registry_upsert_statement(
    session: DbSessionDep,
    rows: list[dict[str, object]],
) -> Any:
    dialect_name = session.get_bind().dialect.name
    table = typing_cast(Any, PromptRegistryEntry.__table__)
    statement: Any
    if dialect_name == "postgresql":
        statement = pg_insert(table).values(rows)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(table).values(rows)
    else:
        raise RuntimeError(f"Prompt registry bulk import is not supported on {dialect_name}.")
    return statement.on_conflict_do_update(
        index_elements=[
            table.c.source_key,
            table.c.entry_index,
        ],
        set_={
            "prompt": statement.excluded.prompt,
            "entry_index_key": statement.excluded.entry_index_key,
            "negative_prompt": statement.excluded.negative_prompt,
            "metadata": statement.excluded.metadata,
            "origin": statement.excluded.origin,
            "updated_at": func.now(),
        },
    )


def _usage_identifier(prompt_id: str) -> PromptIdentifier:
    identifier = parse_prompt_id(prompt_id)
    if identifier is None:
        raise ApiError(
            status_code=422,
            code="PROMPT_ID_INVALID",
            message="Prompt ID must use the form 'source - index'.",
        )
    return identifier


async def _usage_query(
    session: DbSessionDep,
    identifier: PromptIdentifier,
    character_lora: str | None,
) -> Select[tuple[Media, MediaAsset]]:
    """Use the materialized index; preserve legacy evidence recovery during backfill."""

    query = (
        select(Media, MediaAsset)
        .join(MediaAsset, MediaAsset.media_id == Media.id)
        .outerjoin(MediaPromptIndex, MediaPromptIndex.media_id == Media.id)
    )
    missing_index = await session.scalar(
        select(
            exists(
                select(WorkflowSnapshot.id).where(
                    ~exists(
                        select(MediaPromptIndex.media_id).where(
                            MediaPromptIndex.media_id == WorkflowSnapshot.media_id
                        )
                    )
                )
            )
        )
    )
    if missing_index:
        recovered = await _matching_media_fallback(session, identifier)
        query = query.where(Media.id.in_([media.id for media, _asset in recovered]))
    else:
        query = query.where(
            MediaPromptIndex.source_key == identifier.source_key,
            MediaPromptIndex.index_key == identifier.index_key,
        )
    character = _normalized_character_lora(character_lora)
    if character is not None:
        query = query.where(func.lower(func.trim(MediaPromptIndex.character_lora)) == character)
    return query


def _usage_order(
    group_by_character: bool, preferred_character_lora: str | None
) -> tuple[ColumnElement[Any], ...]:
    time_order = (Media.created_at.desc(), Media.id.desc())
    if not group_by_character:
        return time_order
    character = func.coalesce(func.lower(func.trim(MediaPromptIndex.character_lora)), "")
    preferred = _normalized_character_lora(preferred_character_lora)
    priority_order = (case((character == preferred, 0), else_=1),) if preferred else ()
    return (
        *priority_order,
        case((character == "", 1), else_=0),
        character.asc(),
        *time_order,
    )


async def _usage_page(
    session: DbSessionDep,
    query: Select[tuple[Media, MediaAsset]],
    *,
    limit: int,
    offset: int,
    group_by_character: bool,
    preferred_character_lora: str | None,
) -> tuple[int, list[tuple[Media, MediaAsset]]]:
    total = int(await session.scalar(select(func.count()).select_from(query.subquery())) or 0)
    rows = await session.execute(
        query.order_by(*_usage_order(group_by_character, preferred_character_lora))
        .offset(offset)
        .limit(limit)
    )
    return total, [(media, asset) for media, asset in rows]


async def _usage_navigation(
    session: DbSessionDep,
    query: Select[tuple[Media, MediaAsset]],
    media_id: UUID,
    preferred_character_lora: str | None,
) -> MediaNavigationResponse:
    order = _usage_order(True, preferred_character_lora)
    ranked = query.with_only_columns(
        Media.id,
        func.row_number().over(order_by=order).label("position"),
        func.count().over().label("total"),
        func.lag(Media.id).over(order_by=order).label("previous_id"),
        func.lead(Media.id).over(order_by=order).label("next_id"),
    ).subquery()
    row = (await session.execute(select(ranked).where(ranked.c.id == media_id))).one_or_none()
    if row is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_IN_VIEW",
            message="The media record is not part of this prompt usage view.",
        )
    position = int(row.position)
    return MediaNavigationResponse(
        media_id=media_id,
        position=position,
        total=int(row.total),
        previous_id=row.previous_id,
        previous_position=position - 1 if row.previous_id is not None else None,
        next_id=row.next_id,
        next_position=position + 1 if row.next_id is not None else None,
    )


async def _filter_media_by_character(
    session: DbSessionDep,
    matching_media: list[tuple[Media, MediaAsset]],
    character_lora: str | None,
) -> list[tuple[Media, MediaAsset]]:
    if character_lora is None:
        return matching_media
    media_ids = [media.id for media, _asset in matching_media]
    if not media_ids:
        return []
    allowed = set(
        await session.scalars(
            select(MediaPromptIndex.media_id).where(
                MediaPromptIndex.media_id.in_(media_ids),
                func.lower(MediaPromptIndex.character_lora) == character_lora,
            )
        )
    )
    return [(media, asset) for media, asset in matching_media if media.id in allowed]


async def _matching_media_fallback(
    session: DbSessionDep,
    identifier: PromptIdentifier,
) -> list[tuple[Media, MediaAsset]]:
    rows = list(
        (
            await session.execute(
                select(Media, MediaAsset, WorkflowSnapshot)
                .join(MediaAsset, MediaAsset.media_id == Media.id)
                .outerjoin(WorkflowSnapshot, WorkflowSnapshot.media_id == Media.id)
                .order_by(Media.created_at.desc(), Media.id.desc())
            )
        ).all()
    )
    recovery_rows = list(
        await session.execute(
            select(
                WorkflowDisplayRecovery.media_id,
                WorkflowDisplayRecovery.value,
                WorkflowDisplayRecovery.original_sha256,
            ).where(WorkflowDisplayRecovery.field_name == "prompt_id")
        )
    )
    recovery_by_media = {
        media_id: (value, original_sha256) for media_id, value, original_sha256 in recovery_rows
    }
    profiles_by_scope = await load_profiles_by_scope(session)
    matches: list[tuple[Media, MediaAsset]] = []
    for media, asset, snapshot in rows:
        value: str | None = None
        if snapshot is not None:
            fields = saved_fields(snapshot.raw_metadata, snapshot.api_prompt or {})
            saved = fields.get("prompt_id")
            if saved is not None and isinstance(saved.value, str):
                value = saved.value
            else:
                recovered = recovery_by_media.get(media.id)
                if recovered is not None and recovered[1] == asset.sha256:
                    value = recovered[0]
                elif snapshot.api_prompt:
                    value = prompt_id_candidate(snapshot, profiles_by_scope)
                    if value is None:
                        value = structural_prompt_id_candidate(snapshot)
        parsed = parse_prompt_id(value)
        if parsed is not None and _same_identifier(parsed, identifier):
            matches.append((media, asset))
    return matches


def _same_identifier(left: PromptIdentifier, right: PromptIdentifier) -> bool:
    return left.source_key == right.source_key and left.index_key == right.index_key


def _entry_response(
    entry: PromptRegistryEntry,
    *,
    media_count: int = 0,
) -> PromptRegistryEntryResponse:
    return PromptRegistryEntryResponse(
        id=entry.id,
        source=entry.source,
        index=entry.entry_index,
        prompt=entry.prompt,
        negative_prompt=entry.negative_prompt,
        metadata=entry.entry_metadata,
        origin=entry.origin,
        media_count=media_count,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _media_response(
    row: tuple[Media, MediaAsset],
    *,
    is_trash: bool,
    character_lora: str | None,
) -> PromptRegistryMediaResponse:
    media, asset = row
    return PromptRegistryMediaResponse(
        id=media.id,
        kind=media.kind,
        original_filename=asset.original_filename,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        favorite=media.favorite,
        is_trash=is_trash,
        character_lora=character_lora,
        content_rating=media.content_rating,
        preview_url=f"/api/v1/media/{media.id}/preview",
        created_at=media.created_at,
    )
