from __future__ import annotations

from typing import Any
from typing import cast as typing_cast
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import Integer, cast, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.prompt_registry_schemas import (
    PromptRegistryEntryRequest,
    PromptRegistryEntryResponse,
    PromptRegistryImportRequest,
    PromptRegistryImportResponse,
    PromptRegistryLookupResponse,
    PromptRegistryMediaResponse,
    PromptRegistryPageResponse,
)
from comfy_gallery_core.db.models import (
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
)

router = APIRouter(prefix="/api/v1/prompt-registry", tags=["prompt-registry"])


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
                cast(PromptRegistryEntry.entry_index, Integer),
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


@router.get("/lookup", response_model=PromptRegistryLookupResponse)
async def lookup_prompt_registry_entry(
    _principal: PrincipalDep,
    session: DbSessionDep,
    prompt_id: str = Query(min_length=1, max_length=512),
    limit: int = Query(default=48, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PromptRegistryLookupResponse:
    identifier = parse_prompt_id(prompt_id)
    if identifier is None:
        raise ApiError(
            status_code=422,
            code="PROMPT_ID_INVALID",
            message="Prompt ID must use the form 'source - index'.",
        )
    entry = await _find_entry(session, identifier)
    matching_media = await _matching_media(session, identifier)
    media = matching_media[offset : offset + limit]
    display_identifier = (
        PromptIdentifier(source=entry.source, index=entry.entry_index)
        if entry is not None
        else identifier
    )
    return PromptRegistryLookupResponse(
        prompt_id=display_identifier.display,
        source=display_identifier.source,
        index=display_identifier.index,
        entry=_entry_response(entry, media_count=len(matching_media)) if entry else None,
        media=[_media_response(row) for row in media],
        total_media=len(matching_media),
        limit=limit,
        offset=offset,
    )


@router.get("/{entry_id}", response_model=PromptRegistryLookupResponse)
async def get_prompt_registry_entry(
    entry_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
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
    matching_media = await _matching_media(session, identifier)
    media = matching_media[offset : offset + limit]
    return PromptRegistryLookupResponse(
        prompt_id=identifier.display,
        source=identifier.source,
        index=identifier.index,
        entry=_entry_response(entry, media_count=len(matching_media)),
        media=[_media_response(row) for row in media],
        total_media=len(matching_media),
        limit=limit,
        offset=offset,
    )


@router.post("/import", response_model=PromptRegistryImportResponse)
async def import_prompt_registry_entries(
    request: PromptRegistryImportRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> PromptRegistryImportResponse:
    if len(request.model_dump_json().encode("utf-8")) > 8 * 1024 * 1024:
        raise ApiError(
            status_code=413,
            code="PROMPT_REGISTRY_IMPORT_TOO_LARGE",
            message="Prompt registry import payload must be 8 MB or smaller.",
        )

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
    try:
        numeric_index = int(identifier.index)
    except ValueError:
        return None
    return typing_cast(
        PromptRegistryEntry | None,
        await session.scalar(
            select(PromptRegistryEntry).where(
                PromptRegistryEntry.source_key == identifier.source_key,
                cast(PromptRegistryEntry.entry_index, Integer) == numeric_index,
            )
        ),
    )


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
            "negative_prompt": statement.excluded.negative_prompt,
            "metadata": statement.excluded.metadata,
            "origin": statement.excluded.origin,
            "updated_at": func.now(),
        },
    )


async def _matching_media(
    session: DbSessionDep,
    identifier: PromptIdentifier,
) -> list[tuple[Media, MediaAsset]]:
    media_count = int(await session.scalar(select(func.count()).select_from(Media)) or 0)
    indexed_count = int(
        await session.scalar(select(func.count()).select_from(MediaPromptIndex)) or 0
    )
    if media_count == indexed_count:
        rows = list(
            (
                await session.execute(
                    select(Media, MediaAsset)
                    .join(MediaAsset, MediaAsset.media_id == Media.id)
                    .join(MediaPromptIndex, MediaPromptIndex.media_id == Media.id)
                    .where(
                        MediaPromptIndex.source_key == identifier.source_key,
                        MediaPromptIndex.index_value == identifier.index_value,
                    )
                    .order_by(Media.created_at.desc(), Media.id.desc())
                )
            ).all()
        )
        return [(media, asset) for media, asset in rows]
    return await _matching_media_fallback(session, identifier)


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
        parsed = parse_prompt_id(value)
        if parsed is not None and _same_identifier(parsed, identifier):
            matches.append((media, asset))
    return matches


def _same_identifier(left: PromptIdentifier, right: PromptIdentifier) -> bool:
    return left.source_key == right.source_key and left.index_value == right.index_value


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


def _media_response(row: tuple[Media, MediaAsset]) -> PromptRegistryMediaResponse:
    media, asset = row
    return PromptRegistryMediaResponse(
        id=media.id,
        kind=media.kind,
        original_filename=asset.original_filename,
        width=media.width,
        height=media.height,
        duration_seconds=media.duration_seconds,
        favorite=media.favorite,
        content_rating=media.content_rating,
        preview_url=f"/api/v1/media/{media.id}/preview",
        created_at=media.created_at,
    )
