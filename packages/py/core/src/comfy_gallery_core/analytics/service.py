from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.analytics.statistics import summarize_distribution
from comfy_gallery_core.db.models import (
    AnalysisMember,
    AnalysisResult,
    AnalysisRun,
    AnalysisScoreSnapshot,
    CollectionItem,
    ComparisonGroupMember,
    CriterionVersion,
    Evaluation,
    EvaluationScore,
    EvaluationTemplate,
    EvaluationTemplateItem,
    LoraSeries,
    LoraSeriesMember,
    Media,
    MediaTag,
    ModelArtifact,
    ModelReference,
    ModelReferenceGroup,
    ModelUsage,
    ScoreRevision,
    SourceOccurrence,
    User,
    WeightingProfile,
    WorkflowSnapshot,
)

ANALYTICS_CALCULATION_VERSION = "model-observational-v1"
EQUAL_WEIGHT_PROFILE_ID = uuid5(
    NAMESPACE_URL,
    "comfy-gallery:weighting-profile:equal:v1",
)
COMPOSITE_KEY = "__composite__"
SUPPORTED_REPORT_TYPES = {
    "checkpoint",
    "checkpoint_pair",
    "lora",
    "lora_training_series",
    "checkpoint_lora_matrix",
    "lora_combination",
}


@dataclass(frozen=True, slots=True)
class ScorePoint:
    criterion_version_id: UUID
    score_revision_id: UUID
    key: str
    label: str
    state: str
    value: int | None


@dataclass(frozen=True, slots=True)
class SeriesMembership:
    series_id: UUID
    series_name: str
    training_step: int


@dataclass(frozen=True, slots=True)
class ModelUse:
    reference_id: UUID
    artifact_id: UUID | None
    identity_key: str
    identity_label: str
    identity_state: str
    observation_type: str
    architecture_family: str
    pipeline_pattern: str
    slot: str
    usage_order: int
    confidence: float
    series: tuple[SeriesMembership, ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisCandidate:
    media_id: UUID
    media_kind: str
    evaluation_id: UUID | None
    template_id: UUID | None
    template_version: int | None
    evaluation_version: int | None
    progress_state: str | None
    is_trash: bool
    template_criteria: frozenset[str]
    scores: Mapping[str, ScorePoint]
    model_uses: tuple[ModelUse, ...]


@dataclass(frozen=True, slots=True)
class GroupAssignment:
    key: str
    label: str
    dimensions: Mapping[str, object]


@dataclass(slots=True)
class MemberComputation:
    candidate: AnalysisCandidate
    included: bool
    exclusion_reason: str | None
    groups: list[GroupAssignment]
    composite_score: float | None
    included_criterion_keys: list[str]
    weights: dict[str, float]
    model_context: dict[str, object]


@dataclass(frozen=True, slots=True)
class ResultComputation:
    group: GroupAssignment
    criterion_key: str
    criterion_label: str
    eligible_count: int
    scored_count: int
    na_count: int
    not_collected_count: int
    trash_count: int
    coverage: float
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    q1: float | None
    q3: float | None
    ci_low: float | None
    ci_high: float | None
    reference_group_key: str | None
    difference_from_reference: float | None
    effect_size: float | None
    evidence_strength: str
    histogram: list[int]
    context: Mapping[str, object]


@dataclass(slots=True)
class ReportComputation:
    report_type: str
    members: list[MemberComputation]
    results: list[ResultComputation]
    effective_criteria: list[dict[str, object]]
    warnings: list[str]
    context: dict[str, object]

    @property
    def media_count(self) -> int:
        return sum(member.included for member in self.members)

    @property
    def excluded_count(self) -> int:
        return len(self.members) - self.media_count

    @property
    def group_count(self) -> int:
        return len({result.group.key for result in self.results})


async def ensure_equal_weight_profile(session: AsyncSession) -> WeightingProfile:
    profile = await session.get(WeightingProfile, EQUAL_WEIGHT_PROFILE_ID)
    if profile is not None:
        return profile
    profile = WeightingProfile(
        id=EQUAL_WEIGHT_PROFILE_ID,
        stable_key="equal",
        version=1,
        name="Equal weight",
        description="Every collected criterion contributes equally.",
        weights={},
        default_weight=1.0,
        is_builtin=True,
    )
    session.add(profile)
    await session.flush()
    return profile


async def load_analysis_population(
    session: AsyncSession,
    filter_spec: Mapping[str, object],
) -> list[AnalysisCandidate]:
    media_statement = select(Media).where(Media.status.in_(("ready", "ready_with_warnings")))
    media_kind = _optional_str(filter_spec.get("media_kind"))
    if media_kind:
        media_statement = media_statement.where(Media.kind == media_kind)
    collection_id = _optional_uuid(filter_spec.get("collection_id"))
    if collection_id is not None:
        media_statement = media_statement.join(
            CollectionItem,
            CollectionItem.media_id == Media.id,
        ).where(CollectionItem.collection_id == collection_id)
    tag_id = _optional_uuid(filter_spec.get("tag_id"))
    if tag_id is not None:
        media_statement = media_statement.join(
            MediaTag,
            MediaTag.media_id == Media.id,
        ).where(MediaTag.tag_id == tag_id)
    source_root_id = _optional_uuid(filter_spec.get("source_root_id"))
    if source_root_id is not None:
        media_statement = media_statement.join(
            SourceOccurrence,
            SourceOccurrence.media_id == Media.id,
        ).where(
            SourceOccurrence.source_root_id == source_root_id,
            SourceOccurrence.superseded_at.is_(None),
        )
    media = list(await session.scalars(media_statement.order_by(Media.created_at, Media.id)))
    if not media:
        return []

    media_by_id = {item.id: item for item in media}
    module = _optional_str(filter_spec.get("module")) or "core"
    template_ids = _uuid_set(filter_spec.get("template_ids"))
    evaluation_statement = (
        select(Evaluation)
        .join(EvaluationTemplate, EvaluationTemplate.id == Evaluation.template_id)
        .options(
            selectinload(Evaluation.scores)
            .selectinload(EvaluationScore.criterion_version)
            .selectinload(CriterionVersion.criterion),
            selectinload(Evaluation.template)
            .selectinload(EvaluationTemplate.items)
            .selectinload(EvaluationTemplateItem.criterion_version)
            .selectinload(CriterionVersion.criterion),
        )
        .where(
            Evaluation.media_id.in_(media_by_id),
            EvaluationTemplate.module == module,
        )
    )
    if template_ids:
        evaluation_statement = evaluation_statement.where(Evaluation.template_id.in_(template_ids))
    evaluations = list(await session.scalars(evaluation_statement))
    selected_evaluations: dict[UUID, Evaluation] = {}
    for evaluation in evaluations:
        previous = selected_evaluations.get(evaluation.media_id)
        if previous is None or _evaluation_sort_key(evaluation) > _evaluation_sort_key(previous):
            selected_evaluations[evaluation.media_id] = evaluation

    revision_by_score = await _latest_score_revisions(
        session,
        list(selected_evaluations.values()),
    )
    uses_by_media = await _load_model_uses(session, set(media_by_id))
    expanded_filter_spec = dict(filter_spec)
    comparison_group_id = _optional_uuid(filter_spec.get("comparison_group_id"))
    if comparison_group_id is not None:
        comparison_artifact_ids = list(
            await session.scalars(
                select(ComparisonGroupMember.artifact_id).where(
                    ComparisonGroupMember.group_id == comparison_group_id
                )
            )
        )
        configured_artifact_ids = _uuid_set(filter_spec.get("artifact_ids"))
        expanded_filter_spec["artifact_ids"] = [
            str(artifact_id)
            for artifact_id in configured_artifact_ids.union(comparison_artifact_ids)
        ]

    candidates: list[AnalysisCandidate] = []
    for item in media:
        selected_evaluation = selected_evaluations.get(item.id)
        if selected_evaluation is None:
            candidate = AnalysisCandidate(
                media_id=item.id,
                media_kind=item.kind,
                evaluation_id=None,
                template_id=None,
                template_version=None,
                evaluation_version=None,
                progress_state=None,
                is_trash=False,
                template_criteria=frozenset(),
                scores={},
                model_uses=tuple(uses_by_media.get(item.id, ())),
            )
        else:
            template_items = sorted(
                selected_evaluation.template.items,
                key=lambda entry: entry.ordinal,
            )
            template_criteria = frozenset(
                entry.criterion_version.criterion.stable_key for entry in template_items
            )
            scores: dict[str, ScorePoint] = {}
            for score in selected_evaluation.scores:
                revision = revision_by_score.get(
                    (selected_evaluation.id, score.criterion_version_id)
                )
                if revision is None:
                    continue
                criterion = score.criterion_version.criterion
                scores[criterion.stable_key] = ScorePoint(
                    criterion_version_id=score.criterion_version_id,
                    score_revision_id=revision.id,
                    key=criterion.stable_key,
                    label=score.criterion_version.label,
                    state=score.state,
                    value=score.value,
                )
            candidate = AnalysisCandidate(
                media_id=item.id,
                media_kind=item.kind,
                evaluation_id=selected_evaluation.id,
                template_id=selected_evaluation.template_id,
                template_version=selected_evaluation.template.version,
                evaluation_version=selected_evaluation.version,
                progress_state=selected_evaluation.progress_state,
                is_trash=selected_evaluation.is_trash,
                template_criteria=template_criteria,
                scores=scores,
                model_uses=tuple(uses_by_media.get(item.id, ())),
            )
        if _candidate_matches_model_filters(candidate, expanded_filter_spec):
            candidates.append(candidate)
    return candidates


def compute_report(
    candidates: Sequence[AnalysisCandidate],
    report_spec: Mapping[str, object],
    weighting_profile: WeightingProfile,
    *,
    include_trash: bool = False,
) -> ReportComputation:
    report_type = _optional_str(report_spec.get("report_type")) or "checkpoint"
    if report_type not in SUPPORTED_REPORT_TYPES:
        raise ValueError(f"Unsupported analytics report type: {report_type}")
    compatibility_mode = _optional_str(report_spec.get("compatibility_mode")) or "shared"
    selected_keys = _str_list(report_spec.get("criterion_keys"))
    effective_keys = _effective_criteria(
        candidates,
        selected_keys=selected_keys,
        compatibility_mode=compatibility_mode,
    )
    labels = _criterion_labels(candidates)
    effective_criteria: list[dict[str, object]] = [
        {"key": key, "label": labels.get(key, key)} for key in effective_keys
    ]
    weights = _profile_weights(weighting_profile, effective_keys)
    any_role = bool(report_spec.get("any_role", False))

    members: list[MemberComputation] = []
    for candidate in candidates:
        groups = _assign_groups(candidate, report_type=report_type, any_role=any_role)
        reason = _exclusion_reason(
            candidate,
            groups=groups,
            include_trash=include_trash,
        )
        scored_keys = [
            key
            for key in effective_keys
            if (point := candidate.scores.get(key)) is not None
            and point.state == "scored"
            and point.value is not None
            and weights[key] > 0
        ]
        composite = (
            sum(_scored_value(candidate.scores[key]) * weights[key] for key in scored_keys)
            / sum(weights[key] for key in scored_keys)
            if scored_keys
            else None
        )
        members.append(
            MemberComputation(
                candidate=candidate,
                included=reason is None,
                exclusion_reason=reason,
                groups=groups,
                composite_score=composite,
                included_criterion_keys=scored_keys,
                weights=weights,
                model_context=_candidate_model_context(candidate),
            )
        )

    criterion_keys = [COMPOSITE_KEY, *effective_keys]
    reference_group_key = _optional_str(report_spec.get("reference_group_key"))
    result_values = _collect_group_values(members, criterion_keys)
    results: list[ResultComputation] = []
    all_groups = {group.key: group for member in members for group in member.groups}
    for group_key, group in sorted(all_groups.items(), key=lambda entry: entry[1].label.lower()):
        for criterion_key in criterion_keys:
            counts = _group_counts(
                members,
                group_key=group_key,
                criterion_key=criterion_key,
            )
            values = result_values.get((group_key, criterion_key), [])
            reference_values = (
                result_values.get((reference_group_key, criterion_key), [])
                if reference_group_key and reference_group_key != group_key
                else None
            )
            summary = summarize_distribution(
                values,
                eligible_count=counts["eligible"],
                na_count=counts["na"],
                not_collected_count=counts["not_collected"],
                trash_count=counts["trash"],
                seed_material=f"{report_type}:{group_key}:{criterion_key}",
                reference_values=reference_values,
            )
            results.append(
                ResultComputation(
                    group=group,
                    criterion_key=criterion_key,
                    criterion_label=(
                        "Weighted composite"
                        if criterion_key == COMPOSITE_KEY
                        else labels.get(criterion_key, criterion_key)
                    ),
                    eligible_count=summary.eligible_count,
                    scored_count=summary.scored_count,
                    na_count=summary.na_count,
                    not_collected_count=summary.not_collected_count,
                    trash_count=summary.trash_count,
                    coverage=summary.coverage,
                    mean=summary.mean,
                    median=summary.median,
                    minimum=summary.minimum,
                    maximum=summary.maximum,
                    q1=summary.q1,
                    q3=summary.q3,
                    ci_low=summary.ci_low,
                    ci_high=summary.ci_high,
                    reference_group_key=(
                        reference_group_key if reference_values is not None else None
                    ),
                    difference_from_reference=summary.difference_from_reference,
                    effect_size=summary.effect_size,
                    evidence_strength=summary.evidence_strength,
                    histogram=summary.histogram,
                    context=_group_context(members, group_key),
                )
            )

    warnings = _report_warnings(
        members,
        results,
        effective_keys=effective_keys,
        compatibility_mode=compatibility_mode,
    )
    return ReportComputation(
        report_type=report_type,
        members=members,
        results=results,
        effective_criteria=effective_criteria,
        warnings=warnings,
        context={
            "calculation_version": ANALYTICS_CALCULATION_VERSION,
            "compatibility_mode": compatibility_mode,
            "any_role": any_role,
            "interpretation": (
                "These are observational associations within the selected media, "
                "not causal model rankings."
            ),
        },
    )


async def save_analysis_run(
    session: AsyncSession,
    *,
    computation: ReportComputation,
    filter_spec: Mapping[str, object],
    report_spec: Mapping[str, object],
    weighting_profile: WeightingProfile,
    user: User,
    title: str,
    parent_run: AnalysisRun | None = None,
) -> AnalysisRun:
    now = datetime.now(UTC)
    run = AnalysisRun(
        title=title,
        report_type=computation.report_type,
        status="complete",
        filter_spec=dict(filter_spec),
        report_spec=dict(report_spec),
        weighting_profile_id=weighting_profile.id,
        calculation_version=ANALYTICS_CALCULATION_VERSION,
        parent_run_id=parent_run.id if parent_run else None,
        created_by_user_id=user.id,
        media_count=computation.media_count,
        excluded_count=computation.excluded_count,
        group_count=computation.group_count,
        effective_criteria=list(computation.effective_criteria),
        warnings=list(computation.warnings),
        context=dict(computation.context),
        completed_at=now,
    )
    session.add(run)
    await session.flush()

    for member_computation in computation.members:
        candidate = member_computation.candidate
        member = AnalysisMember(
            run_id=run.id,
            media_id=candidate.media_id,
            evaluation_id=candidate.evaluation_id,
            template_id=candidate.template_id,
            evaluation_version=candidate.evaluation_version,
            included=member_computation.included,
            exclusion_reason=member_computation.exclusion_reason,
            group_keys=[
                {
                    "key": group.key,
                    "label": group.label,
                    "dimensions": dict(group.dimensions),
                }
                for group in member_computation.groups
            ],
            model_context=dict(member_computation.model_context),
            composite_score=member_computation.composite_score,
            included_criterion_keys=list(member_computation.included_criterion_keys),
        )
        session.add(member)
        await session.flush()
        if not member_computation.included:
            continue
        for key in computation_criterion_keys(computation):
            point = candidate.scores.get(key)
            if point is None:
                continue
            session.add(
                AnalysisScoreSnapshot(
                    member_id=member.id,
                    criterion_version_id=point.criterion_version_id,
                    score_revision_id=point.score_revision_id,
                    criterion_key=point.key,
                    criterion_label=point.label,
                    score_state=point.state,
                    value=point.value,
                    weight=member_computation.weights[key],
                )
            )

    for result in computation.results:
        session.add(
            AnalysisResult(
                run_id=run.id,
                group_hash=hashlib.sha256(result.group.key.encode("utf-8")).hexdigest(),
                group_key=result.group.key,
                group_label=result.group.label,
                dimensions=dict(result.group.dimensions),
                criterion_key=result.criterion_key,
                criterion_label=result.criterion_label,
                eligible_count=result.eligible_count,
                scored_count=result.scored_count,
                na_count=result.na_count,
                not_collected_count=result.not_collected_count,
                trash_count=result.trash_count,
                coverage=result.coverage,
                mean=result.mean,
                median=result.median,
                minimum=result.minimum,
                maximum=result.maximum,
                q1=result.q1,
                q3=result.q3,
                ci_low=result.ci_low,
                ci_high=result.ci_high,
                reference_group_key=result.reference_group_key,
                difference_from_reference=result.difference_from_reference,
                effect_size=result.effect_size,
                evidence_strength=result.evidence_strength,
                histogram=list(result.histogram),
                context=dict(result.context),
            )
        )
    await session.commit()
    return run


def computation_criterion_keys(computation: ReportComputation) -> list[str]:
    return [str(item["key"]) for item in computation.effective_criteria]


async def _latest_score_revisions(
    session: AsyncSession,
    evaluations: Sequence[Evaluation],
) -> dict[tuple[UUID, UUID], ScoreRevision]:
    if not evaluations:
        return {}
    revisions = list(
        await session.scalars(
            select(ScoreRevision)
            .where(ScoreRevision.evaluation_id.in_([item.id for item in evaluations]))
            .order_by(
                ScoreRevision.evaluation_id,
                ScoreRevision.criterion_version_id,
                ScoreRevision.evaluation_version.desc(),
                ScoreRevision.created_at.desc(),
            )
        )
    )
    latest: dict[tuple[UUID, UUID], ScoreRevision] = {}
    for revision in revisions:
        latest.setdefault(
            (revision.evaluation_id, revision.criterion_version_id),
            revision,
        )
    return latest


async def _load_model_uses(
    session: AsyncSession,
    media_ids: set[UUID],
) -> dict[UUID, list[ModelUse]]:
    if not media_ids:
        return {}
    rows = (
        await session.execute(
            select(
                WorkflowSnapshot.media_id,
                ModelUsage,
                ModelReference,
                ModelArtifact,
                ModelReferenceGroup,
            )
            .join(ModelUsage, ModelUsage.snapshot_id == WorkflowSnapshot.id)
            .join(ModelReference, ModelReference.id == ModelUsage.model_reference_id)
            .outerjoin(ModelArtifact, ModelArtifact.id == ModelUsage.artifact_id)
            .outerjoin(
                ModelReferenceGroup,
                ModelReferenceGroup.id == ModelReference.identity_group_id,
            )
            .where(WorkflowSnapshot.media_id.in_(media_ids))
            .order_by(WorkflowSnapshot.media_id, ModelUsage.usage_order, ModelUsage.id)
        )
    ).all()
    reference_ids = {reference.id for _, _, reference, _, _ in rows}
    series_by_reference: dict[UUID, list[SeriesMembership]] = defaultdict(list)
    if reference_ids:
        series_rows = (
            await session.execute(
                select(LoraSeriesMember, LoraSeries)
                .join(LoraSeries, LoraSeries.id == LoraSeriesMember.series_id)
                .where(LoraSeriesMember.model_reference_id.in_(reference_ids))
            )
        ).all()
        for member, series in series_rows:
            series_by_reference[member.model_reference_id].append(
                SeriesMembership(
                    series_id=series.id,
                    series_name=series.display_name,
                    training_step=member.training_step,
                )
            )

    uses_by_media: dict[UUID, list[ModelUse]] = defaultdict(list)
    for media_id, usage, reference, artifact, identity_group in rows:
        if identity_group is not None and identity_group.status == "confirmed":
            identity_key = f"reference_group:{identity_group.id}"
            identity_label = identity_group.display_name
            identity_state = "alias_confirmed"
        elif artifact is not None:
            identity_key = f"artifact:{artifact.id}"
            identity_label = artifact.display_name
            identity_state = artifact.identity_state
        else:
            identity_key = f"reference:{reference.id}"
            identity_label = reference.raw_value
            identity_state = reference.resolution_state
        uses_by_media[media_id].append(
            ModelUse(
                reference_id=reference.id,
                artifact_id=artifact.id if artifact is not None else None,
                identity_key=identity_key,
                identity_label=identity_label,
                identity_state=identity_state,
                observation_type=usage.observation_type,
                architecture_family=(
                    artifact.architecture_family
                    if artifact is not None and artifact.architecture_family
                    else "Unknown architecture"
                ),
                pipeline_pattern=usage.pipeline_pattern,
                slot=usage.slot,
                usage_order=usage.usage_order,
                confidence=usage.confidence,
                series=tuple(series_by_reference.get(reference.id, ())),
            )
        )
    return uses_by_media


def _candidate_matches_model_filters(
    candidate: AnalysisCandidate,
    filter_spec: Mapping[str, object],
) -> bool:
    uses = candidate.model_uses
    architecture = _optional_str(filter_spec.get("architecture_family"))
    if architecture and not any(use.architecture_family == architecture for use in uses):
        return False
    pipeline = _optional_str(filter_spec.get("pipeline_pattern"))
    if pipeline and not any(use.pipeline_pattern == pipeline for use in uses):
        return False
    slots = set(_str_list(filter_spec.get("slots")))
    if slots and not any(use.slot in slots for use in uses):
        return False
    artifact_ids = _uuid_set(filter_spec.get("artifact_ids"))
    if artifact_ids and not any(use.artifact_id in artifact_ids for use in uses):
        return False
    series_id = _optional_uuid(filter_spec.get("lora_series_id"))
    return not (
        series_id
        and not any(membership.series_id == series_id for use in uses for membership in use.series)
    )


def _effective_criteria(
    candidates: Sequence[AnalysisCandidate],
    *,
    selected_keys: list[str],
    compatibility_mode: str,
) -> list[str]:
    template_sets = [
        set(candidate.template_criteria)
        for candidate in candidates
        if candidate.evaluation_id is not None
    ]
    if not template_sets:
        return []
    available = (
        set.intersection(*template_sets)
        if compatibility_mode == "shared"
        else set.union(*template_sets)
    )
    if selected_keys:
        return [key for key in selected_keys if key in available]
    return sorted(available)


def _profile_weights(
    profile: WeightingProfile,
    criterion_keys: Sequence[str],
) -> dict[str, float]:
    configured = {
        str(key): float(value)
        for key, value in profile.weights.items()
        if isinstance(value, int | float)
    }
    return {key: max(0.0, configured.get(key, profile.default_weight)) for key in criterion_keys}


def _assign_groups(
    candidate: AnalysisCandidate,
    *,
    report_type: str,
    any_role: bool,
) -> list[GroupAssignment]:
    checkpoints = _deduplicate_uses(
        use for use in candidate.model_uses if use.observation_type == "checkpoint_reference"
    )
    loras = _deduplicate_uses(
        use for use in candidate.model_uses if use.observation_type == "lora_reference"
    )
    architecture = (
        " + ".join(sorted({use.architecture_family for use in checkpoints}))
        or "Unknown architecture"
    )
    pipelines = sorted({use.pipeline_pattern for use in (*checkpoints, *loras)})
    pipeline = " + ".join(pipelines) or "unknown"
    groups: list[GroupAssignment] = []

    if report_type == "checkpoint":
        for checkpoint in checkpoints:
            dimensions: dict[str, object] = {
                "checkpoint": checkpoint.identity_key,
                "architecture_family": checkpoint.architecture_family,
                "pipeline_pattern": checkpoint.pipeline_pattern,
            }
            label = checkpoint.identity_label
            if not any_role:
                dimensions["slot"] = checkpoint.slot
                label = f"{label} · {checkpoint.slot}"
            groups.append(_group(dimensions, label))
    elif report_type == "checkpoint_pair" and len(checkpoints) == 2:
        ordered = sorted(checkpoints, key=lambda use: (use.usage_order, use.slot))
        dimensions = {
            "checkpoints": [use.identity_key for use in ordered],
            "slots": [use.slot for use in ordered],
            "architecture_family": architecture,
            "pipeline_pattern": pipeline,
        }
        groups.append(
            _group(
                dimensions,
                " → ".join(f"{use.identity_label} ({use.slot})" for use in ordered),
            )
        )
    elif report_type == "lora":
        for lora in loras:
            groups.append(
                _group(
                    {
                        "lora": lora.identity_key,
                        "architecture_family": architecture,
                        "pipeline_pattern": lora.pipeline_pattern,
                    },
                    lora.identity_label,
                )
            )
    elif report_type == "lora_training_series":
        for lora in loras:
            for membership in lora.series:
                groups.append(
                    _group(
                        {
                            "series_id": str(membership.series_id),
                            "series_name": membership.series_name,
                            "training_step": membership.training_step,
                            "architecture_family": architecture,
                            "pipeline_pattern": lora.pipeline_pattern,
                        },
                        f"{membership.series_name} · step {membership.training_step}",
                    )
                )
    elif report_type == "checkpoint_lora_matrix":
        for checkpoint in checkpoints:
            for lora in loras:
                groups.append(
                    _group(
                        {
                            "checkpoint": checkpoint.identity_key,
                            "checkpoint_label": checkpoint.identity_label,
                            "checkpoint_slot": checkpoint.slot,
                            "lora": lora.identity_key,
                            "lora_label": lora.identity_label,
                            "architecture_family": checkpoint.architecture_family,
                            "pipeline_pattern": checkpoint.pipeline_pattern,
                        },
                        f"{checkpoint.identity_label} x {lora.identity_label}",
                    )
                )
    elif report_type == "lora_combination" and loras:
        ordered_loras = sorted(loras, key=lambda use: use.identity_key)
        groups.append(
            _group(
                {
                    "loras": [use.identity_key for use in ordered_loras],
                    "architecture_family": architecture,
                    "pipeline_pattern": pipeline,
                },
                " + ".join(use.identity_label for use in ordered_loras),
            )
        )
    return _deduplicate_groups(groups)


def _exclusion_reason(
    candidate: AnalysisCandidate,
    *,
    groups: Sequence[GroupAssignment],
    include_trash: bool,
) -> str | None:
    if candidate.evaluation_id is None:
        return "not_evaluated"
    if candidate.progress_state != "complete":
        return "incomplete_evaluation"
    if candidate.is_trash and not include_trash:
        return "trash"
    if not groups:
        return "factor_not_observed"
    return None


def _collect_group_values(
    members: Sequence[MemberComputation],
    criterion_keys: Sequence[str],
) -> dict[tuple[str, str], list[float]]:
    values: dict[tuple[str, str], list[float]] = defaultdict(list)
    for member in members:
        if not member.included:
            continue
        for group in member.groups:
            for criterion_key in criterion_keys:
                value = _member_value(member, criterion_key)
                if value is not None:
                    values[(group.key, criterion_key)].append(value)
    return values


def _group_counts(
    members: Sequence[MemberComputation],
    *,
    group_key: str,
    criterion_key: str,
) -> dict[str, int]:
    eligible = 0
    na_count = 0
    not_collected = 0
    trash = 0
    for member in members:
        if not any(group.key == group_key for group in member.groups):
            continue
        if member.candidate.is_trash:
            trash += 1
        if not member.included:
            continue
        eligible += 1
        if _member_value(member, criterion_key) is not None:
            continue
        if criterion_key == COMPOSITE_KEY:
            collected = [
                member.candidate.scores.get(key)
                for key in member.weights
                if key in member.candidate.template_criteria
            ]
            if collected and all(point is not None and point.state == "na" for point in collected):
                na_count += 1
            else:
                not_collected += 1
            continue
        point = member.candidate.scores.get(criterion_key)
        if point is not None and point.state == "na":
            na_count += 1
        else:
            not_collected += 1
    return {
        "eligible": eligible,
        "na": na_count,
        "not_collected": not_collected,
        "trash": trash,
    }


def _member_value(member: MemberComputation, criterion_key: str) -> float | None:
    if criterion_key == COMPOSITE_KEY:
        return member.composite_score
    point = member.candidate.scores.get(criterion_key)
    if point is None or point.state != "scored" or point.value is None:
        return None
    return float(point.value)


def _scored_value(point: ScorePoint) -> int:
    if point.value is None:
        raise ValueError("A scored analytics point must have a value.")
    return point.value


def _group_context(
    members: Sequence[MemberComputation],
    group_key: str,
) -> dict[str, object]:
    relevant = [
        member
        for member in members
        if member.included and any(group.key == group_key for group in member.groups)
    ]
    co_occurrences: Counter[str] = Counter()
    uncertain = 0
    for member in relevant:
        model_uses = member.candidate.model_uses
        co_occurrences.update(use.identity_label for use in model_uses)
        uncertain += sum(_identity_is_uncertain(use.identity_state) for use in model_uses)
    return {
        "common_model_cooccurrences": [
            {"label": label, "count": count} for label, count in co_occurrences.most_common(5)
        ],
        "identity_uncertainty_occurrences": uncertain,
        "sample_media_ids": [str(member.candidate.media_id) for member in relevant[:20]],
    }


def _candidate_model_context(candidate: AnalysisCandidate) -> dict[str, object]:
    return {
        "uses": [
            {
                "reference_id": str(use.reference_id),
                "artifact_id": str(use.artifact_id) if use.artifact_id else None,
                "identity_key": use.identity_key,
                "identity_label": use.identity_label,
                "identity_state": use.identity_state,
                "observation_type": use.observation_type,
                "architecture_family": use.architecture_family,
                "pipeline_pattern": use.pipeline_pattern,
                "slot": use.slot,
                "usage_order": use.usage_order,
                "confidence": use.confidence,
                "series": [
                    {
                        "series_id": str(item.series_id),
                        "series_name": item.series_name,
                        "training_step": item.training_step,
                    }
                    for item in use.series
                ],
            }
            for use in candidate.model_uses
        ]
    }


def _report_warnings(
    members: Sequence[MemberComputation],
    results: Sequence[ResultComputation],
    *,
    effective_keys: Sequence[str],
    compatibility_mode: str,
) -> list[str]:
    warnings: list[str] = []
    if not members:
        warnings.append("No media matched the selected population filters.")
        return warnings
    included = [member for member in members if member.included]
    if not included:
        warnings.append(
            "No matched media had a complete, eligible evaluation and the requested model factor."
        )
    if not effective_keys:
        warnings.append("No compatible evaluation criteria were available for the composite.")
    if compatibility_mode == "available":
        warnings.append(
            "Available-criteria mode can produce composites from different criterion sets; "
            "inspect criterion coverage before comparing groups."
        )
    uncertain = sum(
        _identity_is_uncertain(use.identity_state)
        for member in included
        for use in member.candidate.model_uses
    )
    if uncertain:
        warnings.append(
            f"{uncertain} model-use occurrence(s) have uncertain or historical identity."
        )
    composite_results = [result for result in results if result.criterion_key == COMPOSITE_KEY]
    group_sizes = [result.scored_count for result in composite_results if result.scored_count]
    if len(group_sizes) >= 2 and max(group_sizes) >= 3 * min(group_sizes):
        warnings.append(
            "Group sample sizes are substantially imbalanced; compare distributions and "
            "uncertainty, not just means."
        )
    insufficient = sum(result.evidence_strength == "insufficient" for result in composite_results)
    if insufficient:
        warnings.append(f"{insufficient} group(s) have insufficient composite-score evidence.")
    return warnings


def _criterion_labels(candidates: Sequence[AnalysisCandidate]) -> dict[str, str]:
    return {
        point.key: point.label for candidate in candidates for point in candidate.scores.values()
    }


def _identity_is_uncertain(identity_state: str) -> bool:
    return identity_state not in {
        "confirmed",
        "hash_matched",
        "hash_verified",
        "registry_known",
        "resolved",
    }


def _evaluation_sort_key(evaluation: Evaluation) -> tuple[int, datetime, int]:
    moment = evaluation.completed_at or evaluation.updated_at
    return (
        int(evaluation.progress_state == "complete"),
        moment,
        evaluation.version,
    )


def _deduplicate_uses(uses: Iterable[ModelUse]) -> list[ModelUse]:
    unique: dict[tuple[str, str, str], ModelUse] = {}
    for use in uses:
        unique.setdefault((use.identity_key, use.pipeline_pattern, use.slot), use)
    return list(unique.values())


def _group(dimensions: Mapping[str, object], label: str) -> GroupAssignment:
    key = json.dumps(dimensions, sort_keys=True, separators=(",", ":"))
    return GroupAssignment(key=key, label=label, dimensions=dict(dimensions))


def _deduplicate_groups(groups: Sequence[GroupAssignment]) -> list[GroupAssignment]:
    return list({group.key: group for group in groups}.values())


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _optional_uuid(value: object) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return None
    return None


def _uuid_set(value: object) -> set[UUID]:
    if not isinstance(value, list | tuple | set):
        return set()
    return {parsed for item in value if (parsed := _optional_uuid(item)) is not None}


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple | set):
        return []
    return [item for item in value if isinstance(item, str)]
