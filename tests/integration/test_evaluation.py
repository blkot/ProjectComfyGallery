from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_api.dependencies import Principal
from comfy_gallery_api.evaluation_schemas import (
    MediaEvaluationModuleUpdateRequest,
    MediaFilterRequest,
    MediaMembershipRequest,
    ReviewSessionUpdateRequest,
)
from comfy_gallery_api.routes.evaluations import (
    _media_scope_query,
    _resolve_membership_media_ids,
    ensure_media_evaluation_context,
    review_summary,
    update_media_evaluation_module,
    update_review_session,
)
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    EvaluationDispositionRevision,
    EvaluationTemplate,
    Media,
    MediaEvaluationModule,
    ReviewSession,
    ReviewSessionItem,
    ScoreRevision,
    User,
)
from comfy_gallery_core.evaluation.catalog import ensure_evaluation_catalog, get_template
from comfy_gallery_core.evaluation.service import (
    ensure_media_evaluations,
    load_evaluation,
    update_score,
    update_trash,
)
from comfy_gallery_core.media.errors import IngestionError


async def test_filter_membership_resolves_all_matching_media_not_only_reviewable() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        ready_image = Media(kind="image", status="ready")
        failed_image = Media(kind="image", status="failed")
        ready_video = Media(kind="video", status="ready")
        session.add_all([ready_image, failed_image, ready_video])
        await session.flush()

        membership_ids = await _resolve_membership_media_ids(
            session,
            MediaMembershipRequest(filter=MediaFilterRequest(kind="image")),
        )
        review_ids = list(
            await session.scalars(_media_scope_query(MediaFilterRequest(kind="image")))
        )

        assert set(membership_ids) == {ready_image.id, failed_image.id}
        assert review_ids == [ready_image.id]

    await engine.dispose()


async def test_v1_catalog_and_evaluation_state_machine_preserve_zero_na_and_revisions() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        media = Media(kind="image", status="ready")
        session.add_all([user, media])
        await session.flush()
        user_id = user.id
        await ensure_evaluation_catalog(session)
        evaluations = await ensure_media_evaluations(
            session,
            media=media,
            reviewer_user_id=user_id,
            optional_modules=set(),
        )
        await session.commit()

        evaluation = await load_evaluation(session, evaluations[0].id)
        criterion_ids = [item.criterion_version_id for item in evaluation.template.items]
        assert len(criterion_ids) == 6
        assert evaluation.progress_state == "not_started"

        evaluation = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=criterion_ids[0],
            expected_version=1,
            state="scored",
            value=0,
            na_reason=None,
            user_id=user_id,
        )
        assert evaluation.progress_state == "in_progress"
        assert evaluation.scores[0].value == 0

        evaluation = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=criterion_ids[1],
            expected_version=2,
            state="na",
            value=None,
            na_reason="No usable prompt",
            user_id=user_id,
        )
        for criterion_id in criterion_ids[2:]:
            evaluation = await update_score(
                session,
                evaluation=evaluation,
                criterion_version_id=criterion_id,
                expected_version=evaluation.version,
                state="scored",
                value=5,
                na_reason=None,
                user_id=user_id,
            )
        assert evaluation.progress_state == "complete"
        assert evaluation.completed_at is not None

        evaluation = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=criterion_ids[0],
            expected_version=evaluation.version,
            state="unset",
            value=None,
            na_reason=None,
            user_id=user_id,
        )
        assert evaluation.progress_state == "in_progress"
        assert evaluation.completed_at is None
        assert (
            await session.scalar(
                select(func.count(ScoreRevision.id)).where(
                    ScoreRevision.evaluation_id == evaluation.id
                )
            )
            == 7
        )

    await engine.dispose()


async def test_trash_is_reversible_and_version_conflicts_do_not_overwrite() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        media = Media(kind="video", status="ready")
        session.add_all([user, media])
        await session.flush()
        user_id = user.id
        await ensure_evaluation_catalog(session)
        evaluations = await ensure_media_evaluations(
            session,
            media=media,
            reviewer_user_id=user_id,
            optional_modules=set(),
        )
        await session.commit()
        evaluation = await load_evaluation(session, evaluations[0].id)
        assert len(evaluation.template.items) == 9

        evaluation = await update_trash(
            session,
            evaluation=evaluation,
            expected_version=1,
            is_trash=True,
            user_id=user_id,
        )
        assert evaluation.is_trash is True
        assert evaluation.progress_state == "not_started"
        evaluation_id = evaluation.id

        try:
            await update_trash(
                session,
                evaluation=evaluation,
                expected_version=1,
                is_trash=False,
                user_id=user_id,
            )
        except IngestionError as error:
            assert error.code == "EVALUATION_VERSION_CONFLICT"
            await session.rollback()
        else:
            raise AssertionError("A stale evaluation version must be rejected.")

        evaluation = await load_evaluation(session, evaluation_id)
        evaluation = await update_trash(
            session,
            evaluation=evaluation,
            expected_version=2,
            is_trash=False,
            user_id=user_id,
        )
        assert evaluation.is_trash is False
        assert (
            await session.scalar(
                select(func.count(EvaluationDispositionRevision.id)).where(
                    EvaluationDispositionRevision.evaluation_id == evaluation.id
                )
            )
            == 2
        )

    await engine.dispose()


async def test_adding_character_module_keeps_completed_core_snapshot_complete() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        media = Media(kind="image", status="ready")
        session.add_all([user, media])
        await session.flush()
        await ensure_evaluation_catalog(session)
        core_evaluation = (
            await ensure_media_evaluations(
                session,
                media=media,
                reviewer_user_id=user.id,
                optional_modules=set(),
            )
        )[0]
        await session.commit()
        core_evaluation = await load_evaluation(session, core_evaluation.id)
        for item in core_evaluation.template.items:
            core_evaluation = await update_score(
                session,
                evaluation=core_evaluation,
                criterion_version_id=item.criterion_version_id,
                expected_version=core_evaluation.version,
                state="scored",
                value=7,
                na_reason=None,
                user_id=user.id,
            )
        assert core_evaluation.progress_state == "complete"

        evaluations = await ensure_media_evaluations(
            session,
            media=media,
            reviewer_user_id=user.id,
            optional_modules={"character"},
        )
        await session.commit()
        core_again = await load_evaluation(session, evaluations[0].id)
        character = await load_evaluation(session, evaluations[1].id)

        assert core_again.id == core_evaluation.id
        assert core_again.progress_state == "complete"
        assert character.progress_state == "not_started"
        assert len(character.template.items) == 2
        assert await session.scalar(select(func.count(EvaluationTemplate.id))) == 4
        assert (await get_template(session, media_kind="image", module="core")).version == 1

    await engine.dispose()


async def test_single_media_context_toggles_modules_without_deleting_scores() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        media = Media(kind="image", status="ready")
        session.add_all([user, media])
        await session.commit()
        principal = Principal(user=user, auth_kind="api_token")

        context = await ensure_media_evaluation_context(
            media_id=media.id,
            principal=principal,
            session=session,
        )
        assert context.progress_state == "not_started"
        assert [evaluation.module for evaluation in context.evaluations] == ["core"]
        assert context.available_modules[0].module == "character"
        assert context.available_modules[0].enabled is False

        context = await update_media_evaluation_module(
            media_id=media.id,
            module="character",
            request=MediaEvaluationModuleUpdateRequest(enabled=True),
            principal=principal,
            session=session,
        )
        assert context.enabled_modules == ["character"]
        assert [evaluation.module for evaluation in context.evaluations] == [
            "core",
            "character",
        ]
        character = next(
            evaluation for evaluation in context.evaluations if evaluation.module == "character"
        )
        character_model = await load_evaluation(session, character.id)
        first_criterion = character_model.template.items[0].criterion_version_id
        await update_score(
            session,
            evaluation=character_model,
            criterion_version_id=first_criterion,
            expected_version=character_model.version,
            state="scored",
            value=8,
            na_reason=None,
            user_id=user.id,
        )

        context = await update_media_evaluation_module(
            media_id=media.id,
            module="character",
            request=MediaEvaluationModuleUpdateRequest(enabled=False),
            principal=principal,
            session=session,
        )
        assert context.enabled_modules == []
        assert [evaluation.module for evaluation in context.evaluations] == ["core"]
        assert context.available_modules[0].has_saved_scores is True
        selection = await session.get(
            MediaEvaluationModule,
            {"media_id": media.id, "module": "character"},
        )
        assert selection is not None
        assert selection.enabled is False

        context = await update_media_evaluation_module(
            media_id=media.id,
            module="character",
            request=MediaEvaluationModuleUpdateRequest(enabled=True),
            principal=principal,
            session=session,
        )
        restored = next(
            evaluation for evaluation in context.evaluations if evaluation.module == "character"
        )
        assert restored.id == character.id
        assert restored.scores[0].value == 8

    await engine.dispose()


async def test_review_session_resume_refreshes_server_updated_timestamp() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        first_media = Media(kind="image", status="ready")
        second_media = Media(kind="image", status="ready")
        session.add_all([user, first_media, second_media])
        await session.flush()
        review_session = ReviewSession(
            name="Resume regression",
            source_kind="selection",
            scope_snapshot={},
            ordering_mode="stable",
            optional_modules=[],
            candidate_count=2,
            created_by_user_id=user.id,
        )
        session.add(review_session)
        await session.flush()
        session.add_all(
            [
                ReviewSessionItem(
                    session_id=review_session.id,
                    media_id=first_media.id,
                    ordinal=0,
                ),
                ReviewSessionItem(
                    session_id=review_session.id,
                    media_id=second_media.id,
                    ordinal=1,
                ),
            ]
        )
        await session.commit()

        response = await update_review_session(
            session_id=review_session.id,
            request=ReviewSessionUpdateRequest(current_cursor=1),
            _principal=Principal(user=user, auth_kind="api_token"),
            session=session,
        )

        assert response.current_cursor == 1
        assert response.candidate_count == 2
        assert response.updated_at is not None
        item = await session.scalar(
            select(ReviewSessionItem).where(
                ReviewSessionItem.session_id == review_session.id,
                ReviewSessionItem.ordinal == 1,
            )
        )
        assert item is not None
        assert item.visited_at is not None

    await engine.dispose()


def test_review_scope_query_is_postgres_safe_when_ordered() -> None:
    query = _media_scope_query(
        MediaFilterRequest(
            source_root_id=UUID("00000000-0000-0000-0000-000000000001"),
            collection_id=UUID("00000000-0000-0000-0000-000000000002"),
            tag_id=UUID("00000000-0000-0000-0000-000000000003"),
        )
    ).order_by(Media.created_at.desc())

    sql = str(query.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]

    assert "SELECT DISTINCT" not in sql
    assert sql.count("EXISTS") == 3


async def test_review_summary_excludes_media_that_cannot_be_reviewed() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="reviewer",
            username_normalized="reviewer",
            password_hash="test",
        )
        ready_media = Media(kind="image", status="ready")
        failed_media = Media(kind="image", status="failed")
        session.add_all([user, ready_media, failed_media])
        await session.flush()
        await ensure_evaluation_catalog(session)
        await ensure_media_evaluations(
            session,
            media=failed_media,
            reviewer_user_id=user.id,
            optional_modules=set(),
        )
        await session.commit()

        response = await review_summary(
            _principal=Principal(user=user, auth_kind="api_token"),
            session=session,
        )

        assert response.not_started_count == 1
        assert response.in_progress_count == 0
        assert response.complete_count == 0
        assert response.trash_count == 0

    await engine.dispose()
