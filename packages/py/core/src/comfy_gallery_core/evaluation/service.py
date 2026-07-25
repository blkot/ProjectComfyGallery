from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.db.models import (
    CriterionVersion,
    Evaluation,
    EvaluationDispositionRevision,
    EvaluationScore,
    EvaluationTemplate,
    EvaluationTemplateItem,
    Media,
    MediaEvaluationModule,
    ScoreRevision,
)
from comfy_gallery_core.evaluation.catalog import get_template
from comfy_gallery_core.media.errors import IngestionError


async def ensure_media_evaluations(
    session: AsyncSession,
    *,
    media: Media,
    reviewer_user_id: UUID,
    optional_modules: set[str],
) -> list[Evaluation]:
    modules = ["core", *sorted(optional_modules)]
    templates = [
        await get_template(session, media_kind=media.kind, module=module) for module in modules
    ]
    existing = list(
        await session.scalars(
            select(Evaluation).where(
                Evaluation.media_id == media.id,
                Evaluation.template_id.in_([template.id for template in templates]),
            )
        )
    )
    by_template = {evaluation.template_id: evaluation for evaluation in existing}
    for template in templates:
        if template.id in by_template:
            continue
        evaluation = Evaluation(
            media_id=media.id,
            template_id=template.id,
            reviewer_user_id=reviewer_user_id,
            evaluation_kind="base" if template.module == "core" else "supplemental",
        )
        session.add(evaluation)
        by_template[template.id] = evaluation
    await session.flush()
    return [by_template[template.id] for template in templates]


async def set_media_evaluation_module(
    session: AsyncSession,
    *,
    media: Media,
    module: str,
    enabled: bool,
    reviewer_user_id: UUID,
) -> MediaEvaluationModule:
    selection = await session.scalar(
        select(MediaEvaluationModule).where(
            MediaEvaluationModule.media_id == media.id,
            MediaEvaluationModule.module == module,
        )
    )
    if selection is None:
        selection = MediaEvaluationModule(
            media_id=media.id,
            module=module,
            enabled=enabled,
        )
        session.add(selection)
    else:
        selection.enabled = enabled
    if enabled:
        await ensure_media_evaluations(
            session,
            media=media,
            reviewer_user_id=reviewer_user_id,
            optional_modules={module},
        )
    await session.flush()
    return selection


async def update_score(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
    criterion_version_id: UUID,
    expected_version: int,
    state: str,
    value: int | None,
    na_reason: str | None,
    user_id: UUID,
) -> Evaluation:
    if state not in {"scored", "na", "unset"}:
        raise IngestionError(
            code="EVALUATION_SCORE_STATE_INVALID",
            message="A criterion must be scored, N/A, or unset.",
        )
    if state == "scored" and (value is None or value < 0 or value > 10):
        raise IngestionError(
            code="EVALUATION_SCORE_INVALID",
            message="A score must be an integer from 0 through 10.",
        )
    if state != "scored":
        value = None
    if state != "na":
        na_reason = None
    belongs = await session.scalar(
        select(EvaluationTemplateItem.template_id).where(
            EvaluationTemplateItem.template_id == evaluation.template_id,
            EvaluationTemplateItem.criterion_version_id == criterion_version_id,
        )
    )
    if belongs is None:
        raise IngestionError(
            code="EVALUATION_CRITERION_NOT_APPLICABLE",
            message="The criterion is not part of this evaluation snapshot.",
        )
    new_version = await _claim_version(
        session,
        evaluation=evaluation,
        expected_version=expected_version,
    )
    score = await session.get(
        EvaluationScore,
        {
            "evaluation_id": evaluation.id,
            "criterion_version_id": criterion_version_id,
        },
    )
    old_state = score.state if score is not None else "unset"
    old_value = score.value if score is not None else None
    old_na_reason = score.na_reason if score is not None else None
    if state == "unset":
        if score is not None:
            await session.delete(score)
    elif score is None:
        session.add(
            EvaluationScore(
                evaluation_id=evaluation.id,
                criterion_version_id=criterion_version_id,
                state=state,
                value=value,
                na_reason=na_reason,
                updated_by_user_id=user_id,
            )
        )
    else:
        score.state = state
        score.value = value
        score.na_reason = na_reason
        score.updated_by_user_id = user_id
    session.add(
        ScoreRevision(
            evaluation_id=evaluation.id,
            criterion_version_id=criterion_version_id,
            old_state=old_state,
            old_value=old_value,
            old_na_reason=old_na_reason,
            new_state=state,
            new_value=value,
            new_na_reason=na_reason,
            evaluation_version=new_version,
            changed_by_user_id=user_id,
        )
    )
    await session.flush()
    await _refresh_progress(session, evaluation)
    await session.commit()
    return await load_evaluation(session, evaluation.id)


async def update_trash(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
    expected_version: int,
    is_trash: bool,
    user_id: UUID,
) -> Evaluation:
    old_is_trash = evaluation.is_trash
    new_version = await _claim_version(
        session,
        evaluation=evaluation,
        expected_version=expected_version,
    )
    evaluation.is_trash = is_trash
    session.add(
        EvaluationDispositionRevision(
            evaluation_id=evaluation.id,
            old_is_trash=old_is_trash,
            new_is_trash=is_trash,
            evaluation_version=new_version,
            changed_by_user_id=user_id,
        )
    )
    await session.commit()
    return await load_evaluation(session, evaluation.id)


async def load_evaluation(session: AsyncSession, evaluation_id: UUID) -> Evaluation:
    evaluation = await session.scalar(
        select(Evaluation)
        .options(
            selectinload(Evaluation.scores),
            selectinload(Evaluation.template)
            .selectinload(EvaluationTemplate.items)
            .selectinload(EvaluationTemplateItem.criterion_version)
            .selectinload(CriterionVersion.criterion),
        )
        .where(Evaluation.id == evaluation_id)
        .execution_options(populate_existing=True)
    )
    if evaluation is None:
        raise IngestionError(
            code="EVALUATION_NOT_FOUND",
            message="The evaluation was not found.",
        )
    return evaluation


async def _claim_version(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
    expected_version: int,
) -> int:
    new_version = await session.scalar(
        update(Evaluation)
        .where(
            Evaluation.id == evaluation.id,
            Evaluation.version == expected_version,
        )
        .values(version=Evaluation.version + 1)
        .returning(Evaluation.version)
    )
    if new_version is None:
        current = await session.scalar(
            select(Evaluation.version).where(Evaluation.id == evaluation.id)
        )
        raise IngestionError(
            code="EVALUATION_VERSION_CONFLICT",
            message="This evaluation changed in another tab. Reload before saving.",
            details={"current_version": current},
        )
    evaluation.version = int(new_version)
    return int(new_version)


async def _refresh_progress(session: AsyncSession, evaluation: Evaluation) -> None:
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(EvaluationTemplateItem)
            .where(EvaluationTemplateItem.template_id == evaluation.template_id)
        )
        or 0
    )
    resolved = int(
        await session.scalar(
            select(func.count())
            .select_from(EvaluationScore)
            .where(EvaluationScore.evaluation_id == evaluation.id)
        )
        or 0
    )
    if resolved == 0:
        evaluation.progress_state = "not_started"
        evaluation.completed_at = None
    elif resolved < total:
        evaluation.progress_state = "in_progress"
        evaluation.completed_at = None
    else:
        evaluation.progress_state = "complete"
        evaluation.completed_at = datetime.now(UTC)
