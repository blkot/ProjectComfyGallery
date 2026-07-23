from __future__ import annotations

import random
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.evaluation_schemas import (
    CollectionResponse,
    CriterionResponse,
    DispositionRevisionResponse,
    EvaluationResponse,
    EvaluationRevisionsResponse,
    EvaluationTemplateResponse,
    MediaFilterRequest,
    MediaMembershipRequest,
    NamedRecordRequest,
    ReviewItemResponse,
    ReviewMediaResponse,
    ReviewPromptResponse,
    ReviewSessionCreateRequest,
    ReviewSessionResponse,
    ReviewSessionUpdateRequest,
    ReviewSummaryResponse,
    SavedFilterRequest,
    SavedFilterResponse,
    ScoreClearRequest,
    ScoreResponse,
    ScoreRevisionResponse,
    ScoreUpdateRequest,
    TagRequest,
    TagResponse,
    TrashUpdateRequest,
)
from comfy_gallery_core.db.models import (
    CollectionItem,
    CriterionVersion,
    Evaluation,
    EvaluationDispositionRevision,
    EvaluationTemplate,
    EvaluationTemplateItem,
    ExtractionRun,
    Media,
    MediaCollection,
    MediaTag,
    ReviewSession,
    ReviewSessionItem,
    SavedFilter,
    ScoreRevision,
    SemanticObservation,
    SourceOccurrence,
    Tag,
    WorkflowNode,
)
from comfy_gallery_core.evaluation.catalog import ensure_evaluation_catalog
from comfy_gallery_core.evaluation.service import (
    ensure_media_evaluations,
    load_evaluation,
    update_score,
    update_trash,
)
from comfy_gallery_core.media.errors import IngestionError

router = APIRouter(prefix="/api/v1", tags=["evaluation"])
REVIEWABLE_MEDIA_STATUSES = ("ready", "ready_with_warnings")


@router.get("/evaluation-templates", response_model=list[EvaluationTemplateResponse])
async def list_evaluation_templates(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[EvaluationTemplateResponse]:
    await ensure_evaluation_catalog(session)
    await session.commit()
    templates = list(
        await session.scalars(
            select(EvaluationTemplate)
            .options(
                selectinload(EvaluationTemplate.items)
                .selectinload(EvaluationTemplateItem.criterion_version)
                .selectinload(CriterionVersion.criterion)
            )
            .order_by(
                EvaluationTemplate.media_kind,
                EvaluationTemplate.module,
                EvaluationTemplate.version,
            )
        )
    )
    return [
        EvaluationTemplateResponse(
            id=template.id,
            stable_key=template.stable_key,
            version=template.version,
            name=template.name,
            media_kind=template.media_kind,
            module=template.module,
            locked=template.locked,
            criteria=[
                _criterion_response(item)
                for item in sorted(template.items, key=lambda item: item.ordinal)
            ],
        )
        for template in templates
    ]


@router.get("/review/summary", response_model=ReviewSummaryResponse)
async def review_summary(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ReviewSummaryResponse:
    counts: dict[str, int] = {
        progress_state: int(count)
        for progress_state, count in (
            await session.execute(
                select(Evaluation.progress_state, func.count(Evaluation.id))
                .join(Media, Media.id == Evaluation.media_id)
                .where(
                    Evaluation.evaluation_kind == "base",
                    Media.status.in_(REVIEWABLE_MEDIA_STATUSES),
                )
                .group_by(Evaluation.progress_state)
            )
        ).all()
    }
    total_media = int(
        await session.scalar(
            select(func.count(Media.id)).where(Media.status.in_(REVIEWABLE_MEDIA_STATUSES))
        )
        or 0
    )
    evaluated = sum(int(value) for value in counts.values())
    return ReviewSummaryResponse(
        not_started_count=total_media - evaluated + int(counts.get("not_started", 0)),
        in_progress_count=int(counts.get("in_progress", 0)),
        complete_count=int(counts.get("complete", 0)),
        trash_count=int(
            await session.scalar(
                select(func.count(Evaluation.id))
                .join(Media, Media.id == Evaluation.media_id)
                .where(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.is_trash.is_(True),
                    Media.status.in_(REVIEWABLE_MEDIA_STATUSES),
                )
            )
            or 0
        ),
        active_session_count=int(
            await session.scalar(
                select(func.count(ReviewSession.id)).where(ReviewSession.status == "active")
            )
            or 0
        ),
    )


@router.get("/evaluations", response_model=list[EvaluationResponse])
async def list_evaluations(
    _principal: PrincipalDep,
    session: DbSessionDep,
    progress_state: str | None = None,
    is_trash: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EvaluationResponse]:
    filters = [Evaluation.evaluation_kind == "base"]
    if progress_state:
        filters.append(Evaluation.progress_state == progress_state)
    if is_trash is not None:
        filters.append(Evaluation.is_trash.is_(is_trash))
    evaluations = list(
        await session.scalars(
            select(Evaluation).where(*filters).order_by(Evaluation.updated_at.desc()).limit(limit)
        )
    )
    return [
        _evaluation_response(await load_evaluation(session, evaluation.id))
        for evaluation in evaluations
    ]


@router.put(
    "/evaluations/{evaluation_id}/scores/{criterion_version_id}",
    response_model=EvaluationResponse,
)
async def set_evaluation_score(
    evaluation_id: UUID,
    criterion_version_id: UUID,
    request: ScoreUpdateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> EvaluationResponse:
    evaluation = await _evaluation_or_404(session, evaluation_id)
    try:
        updated = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=criterion_version_id,
            expected_version=request.expected_version,
            state=request.state,
            value=request.value,
            na_reason=request.na_reason,
            user_id=principal.user.id,
        )
    except IngestionError as error:
        raise _evaluation_api_error(error) from error
    return _evaluation_response(updated)


@router.delete(
    "/evaluations/{evaluation_id}/scores/{criterion_version_id}",
    response_model=EvaluationResponse,
)
async def clear_evaluation_score(
    evaluation_id: UUID,
    criterion_version_id: UUID,
    request: ScoreClearRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> EvaluationResponse:
    evaluation = await _evaluation_or_404(session, evaluation_id)
    try:
        updated = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=criterion_version_id,
            expected_version=request.expected_version,
            state="unset",
            value=None,
            na_reason=None,
            user_id=principal.user.id,
        )
    except IngestionError as error:
        raise _evaluation_api_error(error) from error
    return _evaluation_response(updated)


@router.post("/evaluations/{evaluation_id}/trash", response_model=EvaluationResponse)
async def mark_evaluation_trash(
    evaluation_id: UUID,
    request: TrashUpdateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> EvaluationResponse:
    return await _set_trash(
        session,
        evaluation_id=evaluation_id,
        expected_version=request.expected_version,
        is_trash=True,
        user_id=principal.user.id,
    )


@router.post("/evaluations/{evaluation_id}/restore", response_model=EvaluationResponse)
async def restore_evaluation(
    evaluation_id: UUID,
    request: TrashUpdateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> EvaluationResponse:
    return await _set_trash(
        session,
        evaluation_id=evaluation_id,
        expected_version=request.expected_version,
        is_trash=False,
        user_id=principal.user.id,
    )


@router.get(
    "/evaluations/{evaluation_id}/revisions",
    response_model=EvaluationRevisionsResponse,
)
async def get_evaluation_revisions(
    evaluation_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> EvaluationRevisionsResponse:
    await _evaluation_or_404(session, evaluation_id)
    score_rows = list(
        (
            await session.execute(
                select(ScoreRevision, CriterionVersion)
                .join(
                    CriterionVersion,
                    CriterionVersion.id == ScoreRevision.criterion_version_id,
                )
                .options(selectinload(CriterionVersion.criterion))
                .where(ScoreRevision.evaluation_id == evaluation_id)
                .order_by(ScoreRevision.created_at.desc())
            )
        ).all()
    )
    dispositions = list(
        await session.scalars(
            select(EvaluationDispositionRevision)
            .where(EvaluationDispositionRevision.evaluation_id == evaluation_id)
            .order_by(EvaluationDispositionRevision.created_at.desc())
        )
    )
    return EvaluationRevisionsResponse(
        scores=[
            ScoreRevisionResponse(
                id=revision.id,
                criterion_version_id=revision.criterion_version_id,
                criterion_key=criterion_version.criterion.stable_key,
                old_state=revision.old_state,
                old_value=revision.old_value,
                new_state=revision.new_state,
                new_value=revision.new_value,
                evaluation_version=revision.evaluation_version,
                created_at=revision.created_at,
            )
            for revision, criterion_version in score_rows
        ],
        dispositions=[
            DispositionRevisionResponse(
                id=revision.id,
                old_is_trash=revision.old_is_trash,
                new_is_trash=revision.new_is_trash,
                evaluation_version=revision.evaluation_version,
                created_at=revision.created_at,
            )
            for revision in dispositions
        ],
    )


@router.get("/review-sessions", response_model=list[ReviewSessionResponse])
async def list_review_sessions(
    _principal: PrincipalDep,
    session: DbSessionDep,
    limit: int = Query(default=25, ge=1, le=200),
) -> list[ReviewSessionResponse]:
    sessions = list(
        await session.scalars(
            select(ReviewSession).order_by(ReviewSession.last_opened_at.desc()).limit(limit)
        )
    )
    return [await _session_response(session, item) for item in sessions]


@router.post(
    "/review-sessions",
    response_model=ReviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review_session(
    request: ReviewSessionCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ReviewSessionResponse:
    await ensure_evaluation_catalog(session)
    media_ids, scope_snapshot = await _resolve_scope(session, request)
    if not media_ids:
        raise ApiError(
            status_code=422,
            code="REVIEW_SCOPE_EMPTY",
            message="No media matched this review scope.",
        )
    seed = request.random_seed
    if request.ordering_mode == "random" or request.source_kind == "random":
        seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**63)
        random.Random(seed).shuffle(media_ids)
    media_ids = media_ids[: request.random_limit]
    review_session = ReviewSession(
        name=request.name.strip() if request.name else None,
        source_kind=request.source_kind,
        scope_snapshot=scope_snapshot,
        ordering_mode=request.ordering_mode,
        random_seed=seed,
        optional_modules=list(dict.fromkeys(request.optional_modules)),
        candidate_count=len(media_ids),
        created_by_user_id=principal.user.id,
    )
    session.add(review_session)
    await session.flush()
    session.add_all(
        [
            ReviewSessionItem(
                session_id=review_session.id,
                media_id=media_id,
                ordinal=ordinal,
            )
            for ordinal, media_id in enumerate(media_ids)
        ]
    )
    media_records = list(await session.scalars(select(Media).where(Media.id.in_(media_ids))))
    for media in media_records:
        await ensure_media_evaluations(
            session,
            media=media,
            reviewer_user_id=principal.user.id,
            optional_modules=set(request.optional_modules),
        )
    await session.commit()
    return await _session_response(session, review_session)


@router.get("/review-sessions/{session_id}", response_model=ReviewSessionResponse)
async def get_review_session(
    session_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ReviewSessionResponse:
    return await _session_response(session, await _review_session_or_404(session, session_id))


@router.patch("/review-sessions/{session_id}", response_model=ReviewSessionResponse)
async def update_review_session(
    session_id: UUID,
    request: ReviewSessionUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ReviewSessionResponse:
    review_session = await _review_session_or_404(session, session_id)
    if (
        request.current_cursor is not None
        and request.current_cursor >= review_session.candidate_count
    ):
        raise ApiError(
            status_code=422,
            code="REVIEW_CURSOR_INVALID",
            message="The review position is outside this session.",
        )
    if request.current_cursor is not None:
        review_session.current_cursor = request.current_cursor
        item = await session.scalar(
            select(ReviewSessionItem).where(
                ReviewSessionItem.session_id == review_session.id,
                ReviewSessionItem.ordinal == request.current_cursor,
            )
        )
        if item is not None:
            item.visited_at = datetime.now(UTC)
    if request.status is not None:
        review_session.status = request.status
    review_session.last_opened_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(review_session)
    return await _session_response(session, review_session)


@router.delete(
    "/review-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_review_session(
    session_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> Response:
    review_session = await _review_session_or_404(session, session_id)
    await session.delete(review_session)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/review-sessions/{session_id}/items/{position}",
    response_model=ReviewItemResponse,
)
async def get_review_item(
    session_id: UUID,
    position: int,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ReviewItemResponse:
    review_session = await _review_session_or_404(session, session_id)
    item = await session.scalar(
        select(ReviewSessionItem)
        .options(selectinload(ReviewSessionItem.media))
        .where(
            ReviewSessionItem.session_id == review_session.id,
            ReviewSessionItem.ordinal == position,
        )
    )
    if item is None:
        raise ApiError(
            status_code=404,
            code="REVIEW_ITEM_NOT_FOUND",
            message="The review item was not found.",
        )
    modules = {"core", *[str(value) for value in review_session.optional_modules]}
    evaluations = list(
        (
            await session.execute(
                select(Evaluation)
                .join(EvaluationTemplate)
                .where(
                    Evaluation.media_id == item.media_id,
                    EvaluationTemplate.module.in_(modules),
                )
                .order_by(Evaluation.evaluation_kind)
            )
        ).scalars()
    )
    loaded_evaluations = [
        await load_evaluation(session, evaluation.id) for evaluation in evaluations
    ]
    prompts = await _review_prompts(session, item.media_id)
    return ReviewItemResponse(
        session=await _session_response(session, review_session),
        position=position,
        media=ReviewMediaResponse(
            id=item.media.id,
            kind=item.media.kind,
            preview_url=f"/api/v1/media/{item.media.id}/preview",
            playback_url=f"/api/v1/media/{item.media.id}/playback",
            width=item.media.width,
            height=item.media.height,
            duration_seconds=item.media.duration_seconds,
        ),
        prompts=prompts,
        evaluations=[_evaluation_response(evaluation) for evaluation in loaded_evaluations],
    )


@router.get("/collections", response_model=list[CollectionResponse])
async def list_collections(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[CollectionResponse]:
    records = list(await session.scalars(select(MediaCollection).order_by(MediaCollection.name)))
    return [await _collection_response(session, record) for record in records]


@router.post(
    "/collections",
    response_model=CollectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_collection(
    request: NamedRecordRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> CollectionResponse:
    record = MediaCollection(
        name=request.name.strip(),
        description=request.description,
        created_by_user_id=principal.user.id,
    )
    session.add(record)
    await _commit_name_or_conflict(session, "COLLECTION_NAME_EXISTS")
    return await _collection_response(session, record)


@router.post("/collections/{collection_id}/items", response_model=CollectionResponse)
async def add_collection_items(
    collection_id: UUID,
    request: MediaMembershipRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> CollectionResponse:
    collection = await _collection_or_404(session, collection_id)
    media_ids = await _validate_media_ids(session, request.media_ids)
    existing = set(
        await session.scalars(
            select(CollectionItem.media_id).where(
                CollectionItem.collection_id == collection.id,
                CollectionItem.media_id.in_(media_ids),
            )
        )
    )
    session.add_all(
        [
            CollectionItem(collection_id=collection.id, media_id=media_id)
            for media_id in media_ids
            if media_id not in existing
        ]
    )
    await session.commit()
    return await _collection_response(session, collection)


@router.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_collection(
    collection_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> Response:
    await session.delete(await _collection_or_404(session, collection_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tags", response_model=list[TagResponse])
async def list_tags(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[TagResponse]:
    records = list(await session.scalars(select(Tag).order_by(Tag.name)))
    return [await _tag_response(session, record) for record in records]


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    request: TagRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> TagResponse:
    record = Tag(
        name=request.name.strip(),
        color=request.color,
        created_by_user_id=principal.user.id,
    )
    session.add(record)
    await _commit_name_or_conflict(session, "TAG_NAME_EXISTS")
    return await _tag_response(session, record)


@router.post("/tags/{tag_id}/media", response_model=TagResponse)
async def add_tag_media(
    tag_id: UUID,
    request: MediaMembershipRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> TagResponse:
    tag = await _tag_or_404(session, tag_id)
    media_ids = await _validate_media_ids(session, request.media_ids)
    existing = set(
        await session.scalars(
            select(MediaTag.media_id).where(
                MediaTag.tag_id == tag.id,
                MediaTag.media_id.in_(media_ids),
            )
        )
    )
    session.add_all(
        [
            MediaTag(tag_id=tag.id, media_id=media_id)
            for media_id in media_ids
            if media_id not in existing
        ]
    )
    await session.commit()
    return await _tag_response(session, tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(
    tag_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> Response:
    await session.delete(await _tag_or_404(session, tag_id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/saved-filters", response_model=list[SavedFilterResponse])
async def list_saved_filters(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[SavedFilterResponse]:
    records = list(await session.scalars(select(SavedFilter).order_by(SavedFilter.name)))
    return [_saved_filter_response(record) for record in records]


@router.post(
    "/saved-filters",
    response_model=SavedFilterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_filter(
    request: SavedFilterRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> SavedFilterResponse:
    record = SavedFilter(
        name=request.name.strip(),
        expression=request.expression.model_dump(mode="json", exclude_none=True),
        sort_spec=[],
        created_by_user_id=principal.user.id,
    )
    session.add(record)
    await _commit_name_or_conflict(session, "SAVED_FILTER_NAME_EXISTS")
    return _saved_filter_response(record)


@router.delete(
    "/saved-filters/{saved_filter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_saved_filter(
    saved_filter_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> Response:
    record = await session.get(SavedFilter, saved_filter_id)
    if record is None:
        raise ApiError(
            status_code=404,
            code="SAVED_FILTER_NOT_FOUND",
            message="The saved filter was not found.",
        )
    await session.delete(record)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _resolve_scope(
    session: AsyncSession,
    request: ReviewSessionCreateRequest,
) -> tuple[list[UUID], dict[str, object]]:
    media_filter = request.filter or MediaFilterRequest()
    snapshot: dict[str, object] = {
        "source_kind": request.source_kind,
        "filter": media_filter.model_dump(mode="json", exclude_none=True),
    }
    if request.source_kind == "selection":
        media_ids = await _validate_reviewable_media_ids(session, request.media_ids)
        return media_ids, {
            **snapshot,
            "media_ids": [str(value) for value in media_ids],
        }
    if request.source_kind == "collection":
        if request.collection_id is None:
            raise ApiError(
                status_code=422,
                code="COLLECTION_REQUIRED",
                message="Choose a collection.",
            )
        await _collection_or_404(session, request.collection_id)
        media_filter.collection_id = request.collection_id
    elif request.source_kind == "source":
        if request.source_root_id is None:
            raise ApiError(
                status_code=422,
                code="SOURCE_ROOT_REQUIRED",
                message="Choose a source root.",
            )
        media_filter.source_root_id = request.source_root_id
    elif request.source_kind == "saved_filter":
        if request.saved_filter_id is None:
            raise ApiError(
                status_code=422,
                code="SAVED_FILTER_REQUIRED",
                message="Choose a saved filter.",
            )
        record = await session.get(SavedFilter, request.saved_filter_id)
        if record is None:
            raise ApiError(
                status_code=404,
                code="SAVED_FILTER_NOT_FOUND",
                message="The saved filter was not found.",
            )
        media_filter = MediaFilterRequest.model_validate(record.expression)
        snapshot["saved_filter_id"] = str(record.id)
        snapshot["saved_filter_version"] = record.version
        snapshot["filter"] = record.expression
    elif request.source_kind == "in_progress":
        media_filter.evaluation_state = "in_progress"
        media_filter.trash = False
    query = _media_scope_query(media_filter)
    media_ids = list(await session.scalars(query.order_by(Media.created_at.desc())))
    return media_ids, snapshot


def _media_scope_query(media_filter: MediaFilterRequest) -> Select[tuple[UUID]]:
    query = select(Media.id).where(Media.status.in_(REVIEWABLE_MEDIA_STATUSES))
    if media_filter.kind:
        query = query.where(Media.kind == media_filter.kind)
    if media_filter.status:
        query = query.where(Media.status == media_filter.status)
    if media_filter.workflow_status:
        query = query.where(Media.workflow_snapshot.has(parse_status=media_filter.workflow_status))
    if media_filter.source_root_id:
        query = query.where(
            Media.source_occurrences.any(
                and_(
                    SourceOccurrence.source_root_id == media_filter.source_root_id,
                    SourceOccurrence.superseded_at.is_(None),
                )
            )
        )
    if media_filter.collection_id:
        query = query.where(
            Media.collection_memberships.any(
                CollectionItem.collection_id == media_filter.collection_id
            )
        )
    if media_filter.tag_id:
        query = query.where(Media.tag_memberships.any(MediaTag.tag_id == media_filter.tag_id))
    if media_filter.evaluation_state == "not_started":
        query = query.where(
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
    elif media_filter.evaluation_state:
        query = query.where(
            Media.evaluations.any(
                and_(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.progress_state == media_filter.evaluation_state,
                )
            )
        )
    if media_filter.trash is not None:
        query = query.where(
            Media.evaluations.any(
                and_(
                    Evaluation.evaluation_kind == "base",
                    Evaluation.is_trash.is_(media_filter.trash),
                )
            )
        )
    return query


async def _session_response(
    session: AsyncSession,
    review_session: ReviewSession,
) -> ReviewSessionResponse:
    states = list(
        (
            await session.execute(
                select(
                    ReviewSessionItem.media_id,
                    Evaluation.progress_state,
                )
                .join(Evaluation, Evaluation.media_id == ReviewSessionItem.media_id)
                .join(EvaluationTemplate, EvaluationTemplate.id == Evaluation.template_id)
                .where(
                    ReviewSessionItem.session_id == review_session.id,
                    EvaluationTemplate.module.in_(
                        {"core", *[str(value) for value in review_session.optional_modules]}
                    ),
                )
            )
        ).all()
    )
    by_media: dict[UUID, list[str]] = {}
    for media_id, progress_state in states:
        by_media.setdefault(media_id, []).append(progress_state)
    counts = {"not_started": 0, "in_progress": 0, "complete": 0}
    for item_states in by_media.values():
        if item_states and all(value == "complete" for value in item_states):
            counts["complete"] += 1
        elif any(value != "not_started" for value in item_states):
            counts["in_progress"] += 1
        else:
            counts["not_started"] += 1
    counts["not_started"] += review_session.candidate_count - len(by_media)
    return ReviewSessionResponse(
        id=review_session.id,
        name=review_session.name,
        source_kind=review_session.source_kind,
        scope_snapshot=review_session.scope_snapshot,
        ordering_mode=review_session.ordering_mode,
        random_seed=review_session.random_seed,
        optional_modules=[str(value) for value in review_session.optional_modules],
        status=review_session.status,
        current_cursor=review_session.current_cursor,
        candidate_count=review_session.candidate_count,
        progress_counts=counts,
        last_opened_at=review_session.last_opened_at,
        created_at=review_session.created_at,
        updated_at=review_session.updated_at,
    )


def _evaluation_response(evaluation: Evaluation) -> EvaluationResponse:
    score_by_criterion = {score.criterion_version_id: score for score in evaluation.scores}
    criteria = []
    scores = []
    for item in evaluation.template.items:
        version = item.criterion_version
        criteria.append(_criterion_response(item))
        score = score_by_criterion.get(version.id)
        if score is not None:
            scores.append(
                ScoreResponse(
                    criterion_version_id=score.criterion_version_id,
                    state=score.state,
                    value=score.value,
                    na_reason=score.na_reason,
                    updated_at=score.updated_at,
                )
            )
    return EvaluationResponse(
        id=evaluation.id,
        media_id=evaluation.media_id,
        template_id=evaluation.template_id,
        template_name=evaluation.template.name,
        template_version=evaluation.template.version,
        evaluation_kind=evaluation.evaluation_kind,
        progress_state=evaluation.progress_state,
        is_trash=evaluation.is_trash,
        version=evaluation.version,
        completed_at=evaluation.completed_at,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        criteria=criteria,
        scores=scores,
    )


async def _review_prompts(
    session: AsyncSession,
    media_id: UUID,
) -> list[ReviewPromptResponse]:
    rows = list(
        (
            await session.execute(
                select(SemanticObservation, WorkflowNode)
                .join(ExtractionRun, ExtractionRun.id == SemanticObservation.run_id)
                .outerjoin(WorkflowNode, WorkflowNode.id == SemanticObservation.node_id)
                .where(
                    ExtractionRun.is_current.is_(True),
                    ExtractionRun.snapshot.has(media_id=media_id),
                    SemanticObservation.observation_type == "prompt",
                )
                .order_by(SemanticObservation.created_at, SemanticObservation.id)
            )
        ).all()
    )
    prompts = []
    for observation, node in rows:
        if not isinstance(observation.value, str):
            continue
        evidence = observation.evidence
        label = (
            observation.role
            or (str(evidence.get("input_name")) if evidence.get("input_name") else None)
            or (node.title if node is not None else None)
            or (node.class_type if node is not None else None)
            or "Prompt"
        )
        prompts.append(
            ReviewPromptResponse(
                role=observation.role,
                label=label,
                text=observation.value,
            )
        )
    return prompts


async def _set_trash(
    session: AsyncSession,
    *,
    evaluation_id: UUID,
    expected_version: int,
    is_trash: bool,
    user_id: UUID,
) -> EvaluationResponse:
    evaluation = await _evaluation_or_404(session, evaluation_id)
    try:
        updated = await update_trash(
            session,
            evaluation=evaluation,
            expected_version=expected_version,
            is_trash=is_trash,
            user_id=user_id,
        )
    except IngestionError as error:
        raise _evaluation_api_error(error) from error
    return _evaluation_response(updated)


async def _evaluation_or_404(
    session: AsyncSession,
    evaluation_id: UUID,
) -> Evaluation:
    evaluation = await session.get(Evaluation, evaluation_id)
    if evaluation is None:
        raise ApiError(
            status_code=404,
            code="EVALUATION_NOT_FOUND",
            message="The evaluation was not found.",
        )
    return evaluation


async def _review_session_or_404(
    session: AsyncSession,
    session_id: UUID,
) -> ReviewSession:
    review_session = await session.get(ReviewSession, session_id)
    if review_session is None:
        raise ApiError(
            status_code=404,
            code="REVIEW_SESSION_NOT_FOUND",
            message="The review session was not found.",
        )
    return review_session


async def _collection_or_404(
    session: AsyncSession,
    collection_id: UUID,
) -> MediaCollection:
    record = await session.get(MediaCollection, collection_id)
    if record is None:
        raise ApiError(
            status_code=404,
            code="COLLECTION_NOT_FOUND",
            message="The collection was not found.",
        )
    return record


async def _tag_or_404(session: AsyncSession, tag_id: UUID) -> Tag:
    record = await session.get(Tag, tag_id)
    if record is None:
        raise ApiError(status_code=404, code="TAG_NOT_FOUND", message="The tag was not found.")
    return record


async def _validate_media_ids(
    session: AsyncSession,
    media_ids: list[UUID],
) -> list[UUID]:
    unique_ids = list(dict.fromkeys(media_ids))
    found = set(await session.scalars(select(Media.id).where(Media.id.in_(unique_ids))))
    if len(found) != len(unique_ids):
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="One or more media records were not found.",
        )
    return unique_ids


async def _validate_reviewable_media_ids(
    session: AsyncSession,
    media_ids: list[UUID],
) -> list[UUID]:
    unique_ids = await _validate_media_ids(session, media_ids)
    reviewable = set(
        await session.scalars(
            select(Media.id).where(
                Media.id.in_(unique_ids),
                Media.status.in_(REVIEWABLE_MEDIA_STATUSES),
            )
        )
    )
    if len(reviewable) != len(unique_ids):
        raise ApiError(
            status_code=422,
            code="MEDIA_NOT_REVIEWABLE",
            message="One or more selected media records are not ready for review.",
        )
    return unique_ids


async def _collection_response(
    session: AsyncSession,
    record: MediaCollection,
) -> CollectionResponse:
    count = int(
        await session.scalar(
            select(func.count(CollectionItem.media_id)).where(
                CollectionItem.collection_id == record.id
            )
        )
        or 0
    )
    return CollectionResponse(
        id=record.id,
        name=record.name,
        description=record.description,
        item_count=count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _tag_response(session: AsyncSession, record: Tag) -> TagResponse:
    count = int(
        await session.scalar(
            select(func.count(MediaTag.media_id)).where(MediaTag.tag_id == record.id)
        )
        or 0
    )
    return TagResponse(
        id=record.id,
        name=record.name,
        color=record.color,
        item_count=count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _saved_filter_response(record: SavedFilter) -> SavedFilterResponse:
    return SavedFilterResponse(
        id=record.id,
        name=record.name,
        expression=record.expression,
        version=record.version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _criterion_response(item: EvaluationTemplateItem) -> CriterionResponse:
    version = item.criterion_version
    criterion = version.criterion
    return CriterionResponse(
        criterion_version_id=version.id,
        stable_key=criterion.stable_key,
        module=criterion.module,
        version=version.version,
        label=version.label,
        guidance=version.guidance,
        anchor_0=version.anchor_0,
        anchor_5=version.anchor_5,
        anchor_10=version.anchor_10,
        required=item.required,
        allow_na=item.allow_na,
    )


async def _commit_name_or_conflict(session: AsyncSession, code: str) -> None:
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise ApiError(
            status_code=409,
            code=code,
            message="A record with that name already exists.",
        ) from error


def _evaluation_api_error(error: IngestionError) -> ApiError:
    return ApiError(
        status_code=409 if error.code == "EVALUATION_VERSION_CONFLICT" else 422,
        code=error.code,
        message=error.message,
        details=error.details,
    )
