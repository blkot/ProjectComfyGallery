from __future__ import annotations

import re
from functools import partial
from uuid import UUID

import anyio
from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_api.analytics_schemas import (
    AnalysisFilterRequest,
    AnalysisMediaResponse,
    AnalysisOption,
    AnalysisOptionsResponse,
    AnalysisPreviewRequest,
    AnalysisReportResponse,
    AnalysisResultResponse,
    AnalysisRunCreateRequest,
    AnalysisRunDetailResponse,
    AnalysisRunSummaryResponse,
    WeightingProfileCreateRequest,
    WeightingProfileResponse,
    WeightingProfileVersionRequest,
)
from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_core.analytics.service import (
    ReportComputation,
    compute_report,
    ensure_equal_weight_profile,
    load_analysis_population,
    save_analysis_run,
)
from comfy_gallery_core.db.models import (
    AnalysisMember,
    AnalysisResult,
    AnalysisRun,
    ComparisonGroup,
    Criterion,
    EvaluationTemplate,
    LoraSeries,
    ModelArtifact,
    ModelUsage,
    WeightingProfile,
)

router = APIRouter(prefix="/api/v1", tags=["analytics"])


@router.get("/analysis/options", response_model=AnalysisOptionsResponse)
async def analysis_options(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> AnalysisOptionsResponse:
    templates = list(
        await session.scalars(
            select(EvaluationTemplate).order_by(
                EvaluationTemplate.module,
                EvaluationTemplate.media_kind,
                EvaluationTemplate.version.desc(),
            )
        )
    )
    criteria = list(
        await session.scalars(
            select(Criterion).where(Criterion.active.is_(True)).order_by(Criterion.stable_key)
        )
    )
    artifacts = list(
        await session.scalars(
            select(ModelArtifact).order_by(
                ModelArtifact.artifact_type,
                ModelArtifact.display_name,
            )
        )
    )
    groups = list(
        await session.scalars(
            select(ComparisonGroup)
            .where(ComparisonGroup.enabled.is_(True))
            .order_by(ComparisonGroup.name)
        )
    )
    series = list(await session.scalars(select(LoraSeries).order_by(LoraSeries.display_name)))
    architecture_families = [
        value
        for value in await session.scalars(
            select(ModelArtifact.architecture_family)
            .where(ModelArtifact.architecture_family.is_not(None))
            .distinct()
            .order_by(ModelArtifact.architecture_family)
        )
        if value
    ]
    pipeline_patterns = list(
        await session.scalars(
            select(ModelUsage.pipeline_pattern).distinct().order_by(ModelUsage.pipeline_pattern)
        )
    )
    slots = list(
        await session.scalars(select(ModelUsage.slot).distinct().order_by(ModelUsage.slot))
    )
    return AnalysisOptionsResponse(
        templates=[
            AnalysisOption(
                id=str(template.id),
                label=f"{template.name} v{template.version}",
                metadata={
                    "module": template.module,
                    "media_kind": template.media_kind,
                },
            )
            for template in templates
        ],
        criteria=[
            AnalysisOption(
                id=criterion.stable_key,
                label=criterion.stable_key.replace("_", " ").title(),
                metadata={
                    "module": criterion.module,
                    "media_kind": criterion.media_kind,
                },
            )
            for criterion in criteria
        ],
        artifacts=[
            AnalysisOption(
                id=str(artifact.id),
                label=artifact.display_name,
                metadata={
                    "artifact_type": artifact.artifact_type,
                    "architecture_family": artifact.architecture_family,
                    "identity_state": artifact.identity_state,
                    "availability": artifact.availability,
                },
            )
            for artifact in artifacts
        ],
        comparison_groups=[AnalysisOption(id=str(group.id), label=group.name) for group in groups],
        lora_series=[
            AnalysisOption(
                id=str(item.id),
                label=item.display_name,
                metadata={"source": item.source},
            )
            for item in series
        ],
        architecture_families=architecture_families,
        pipeline_patterns=pipeline_patterns,
        slots=slots,
    )


@router.get("/weighting-profiles", response_model=list[WeightingProfileResponse])
async def list_weighting_profiles(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[WeightingProfileResponse]:
    await ensure_equal_weight_profile(session)
    await session.commit()
    profiles = list(
        await session.scalars(
            select(WeightingProfile).order_by(
                WeightingProfile.stable_key,
                WeightingProfile.version.desc(),
            )
        )
    )
    return [WeightingProfileResponse.model_validate(profile) for profile in profiles]


@router.post(
    "/weighting-profiles",
    response_model=WeightingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_weighting_profile(
    request: WeightingProfileCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> WeightingProfileResponse:
    _validate_weights(request.weights)
    stable_key = await _unique_profile_key(session, request.name)
    profile = WeightingProfile(
        stable_key=stable_key,
        version=1,
        name=request.name.strip(),
        description=request.description,
        weights=dict(request.weights),
        default_weight=request.default_weight,
        is_builtin=False,
        created_by_user_id=principal.user.id,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return WeightingProfileResponse.model_validate(profile)


@router.post(
    "/weighting-profiles/{profile_id}/versions",
    response_model=WeightingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_weighting_profile_version(
    profile_id: UUID,
    request: WeightingProfileVersionRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> WeightingProfileResponse:
    source = await _profile_or_404(session, profile_id)
    _validate_weights(request.weights)
    latest_version = int(
        await session.scalar(
            select(func.max(WeightingProfile.version)).where(
                WeightingProfile.stable_key == source.stable_key
            )
        )
        or 0
    )
    profile = WeightingProfile(
        stable_key=source.stable_key,
        version=latest_version + 1,
        name=request.name or source.name,
        description=request.description,
        weights=dict(request.weights),
        default_weight=request.default_weight,
        is_builtin=False,
        created_by_user_id=principal.user.id,
    )
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return WeightingProfileResponse.model_validate(profile)


@router.post("/analysis/previews", response_model=AnalysisReportResponse)
async def preview_analysis(
    request: AnalysisPreviewRequest,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> AnalysisReportResponse:
    computation = await _compute(session, request.filter, request.spec.model_dump(mode="json"))
    return _computation_response(computation)


@router.post(
    "/analysis/runs",
    response_model=AnalysisRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_run(
    request: AnalysisRunCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> AnalysisRunDetailResponse:
    filter_spec = request.filter.model_dump(mode="json", exclude_none=True)
    report_spec = request.spec.model_dump(mode="json", exclude_none=True)
    profile = await _selected_profile(session, request.spec.weighting_profile_id)
    candidates = await load_analysis_population(session, filter_spec)
    computation = await anyio.to_thread.run_sync(
        partial(
            compute_report,
            candidates,
            report_spec,
            profile,
            include_trash=request.filter.include_trash,
        )
    )
    run = await save_analysis_run(
        session,
        computation=computation,
        filter_spec=filter_spec,
        report_spec=report_spec,
        weighting_profile=profile,
        user=principal.user,
        title=request.title.strip(),
    )
    return await _run_detail(session, run.id)


@router.get("/analysis/runs", response_model=list[AnalysisRunSummaryResponse])
async def list_analysis_runs(
    _principal: PrincipalDep,
    session: DbSessionDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AnalysisRunSummaryResponse]:
    runs = list(
        await session.scalars(
            select(AnalysisRun).order_by(AnalysisRun.created_at.desc()).limit(limit)
        )
    )
    return [_run_summary(run) for run in runs]


@router.get("/analysis/runs/{run_id}", response_model=AnalysisRunDetailResponse)
async def get_analysis_run(
    run_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> AnalysisRunDetailResponse:
    return await _run_detail(session, run_id)


@router.post(
    "/analysis/runs/{run_id}/rerun",
    response_model=AnalysisRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rerun_analysis(
    run_id: UUID,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> AnalysisRunDetailResponse:
    source = await _run_or_404(session, run_id)
    profile = await _profile_or_404(session, source.weighting_profile_id)
    candidates = await load_analysis_population(session, source.filter_spec)
    computation = await anyio.to_thread.run_sync(
        partial(
            compute_report,
            candidates,
            source.report_spec,
            profile,
            include_trash=bool(source.filter_spec.get("include_trash", False)),
        )
    )
    run = await save_analysis_run(
        session,
        computation=computation,
        filter_spec=source.filter_spec,
        report_spec=source.report_spec,
        weighting_profile=profile,
        user=principal.user,
        title=f"{source.title} (rerun)",
        parent_run=source,
    )
    return await _run_detail(session, run.id)


@router.get(
    "/analysis/runs/{run_id}/media",
    response_model=list[AnalysisMediaResponse],
)
async def analysis_run_media(
    run_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    group_key: str | None = None,
    included: bool | None = True,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AnalysisMediaResponse]:
    await _run_or_404(session, run_id)
    statement = select(AnalysisMember).where(AnalysisMember.run_id == run_id)
    if included is not None:
        statement = statement.where(AnalysisMember.included.is_(included))
    members = list(await session.scalars(statement.order_by(AnalysisMember.media_id)))
    if group_key:
        members = [
            member
            for member in members
            if any(
                isinstance(group, dict) and group.get("key") == group_key
                for group in member.group_keys
            )
        ]
    members = members[:limit]
    return [
        AnalysisMediaResponse(
            media_id=member.media_id,
            evaluation_id=member.evaluation_id,
            included=member.included,
            exclusion_reason=member.exclusion_reason,
            composite_score=member.composite_score,
            group_keys=member.group_keys,
            preview_url=f"/api/v1/media/{member.media_id}/preview",
        )
        for member in members
    ]


async def _compute(
    session: AsyncSession,
    filter_request: AnalysisFilterRequest,
    report_spec: dict[str, object],
) -> ReportComputation:
    filter_spec = filter_request.model_dump(mode="json", exclude_none=True)
    profile_id = report_spec.get("weighting_profile_id")
    profile = await _selected_profile(
        session,
        UUID(profile_id) if isinstance(profile_id, str) and profile_id else None,
    )
    candidates = await load_analysis_population(session, filter_spec)
    return await anyio.to_thread.run_sync(
        partial(
            compute_report,
            candidates,
            report_spec,
            profile,
            include_trash=filter_request.include_trash,
        )
    )


async def _selected_profile(
    session: AsyncSession,
    profile_id: UUID | None,
) -> WeightingProfile:
    if profile_id is None:
        profile = await ensure_equal_weight_profile(session)
        await session.commit()
        return profile
    return await _profile_or_404(session, profile_id)


async def _profile_or_404(
    session: AsyncSession,
    profile_id: UUID,
) -> WeightingProfile:
    profile = await session.get(WeightingProfile, profile_id)
    if profile is None:
        raise ApiError(
            status_code=404,
            code="WEIGHTING_PROFILE_NOT_FOUND",
            message="The weighting profile was not found.",
        )
    return profile


async def _run_or_404(session: AsyncSession, run_id: UUID) -> AnalysisRun:
    run = await session.get(AnalysisRun, run_id)
    if run is None:
        raise ApiError(
            status_code=404,
            code="ANALYSIS_RUN_NOT_FOUND",
            message="The saved analysis run was not found.",
        )
    return run


async def _run_detail(
    session: AsyncSession,
    run_id: UUID,
) -> AnalysisRunDetailResponse:
    run = await session.scalar(
        select(AnalysisRun)
        .options(selectinload(AnalysisRun.results))
        .where(AnalysisRun.id == run_id)
    )
    if run is None:
        raise ApiError(
            status_code=404,
            code="ANALYSIS_RUN_NOT_FOUND",
            message="The saved analysis run was not found.",
        )
    summary = _run_summary(run)
    return AnalysisRunDetailResponse(
        **summary.model_dump(),
        filter_spec=run.filter_spec,
        report_spec=run.report_spec,
        calculation_version=run.calculation_version,
        effective_criteria=run.effective_criteria,
        context=run.context,
        results=[_stored_result_response(result) for result in run.results],
    )


def _run_summary(run: AnalysisRun) -> AnalysisRunSummaryResponse:
    return AnalysisRunSummaryResponse(
        id=run.id,
        title=run.title,
        report_type=run.report_type,
        status=run.status,
        parent_run_id=run.parent_run_id,
        weighting_profile_id=run.weighting_profile_id,
        media_count=run.media_count,
        excluded_count=run.excluded_count,
        group_count=run.group_count,
        warnings=run.warnings,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


def _computation_response(computation: ReportComputation) -> AnalysisReportResponse:
    return AnalysisReportResponse(
        report_type=computation.report_type,
        media_count=computation.media_count,
        excluded_count=computation.excluded_count,
        group_count=computation.group_count,
        effective_criteria=computation.effective_criteria,
        warnings=computation.warnings,
        context=computation.context,
        results=[
            AnalysisResultResponse(
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
                histogram=result.histogram,
                context=dict(result.context),
            )
            for result in computation.results
        ],
    )


def _stored_result_response(result: AnalysisResult) -> AnalysisResultResponse:
    return AnalysisResultResponse(
        id=result.id,
        group_key=result.group_key,
        group_label=result.group_label,
        dimensions=result.dimensions,
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
        histogram=[
            int(value) if isinstance(value, int | float) else 0 for value in result.histogram
        ],
        context=result.context,
    )


def _validate_weights(weights: dict[str, float]) -> None:
    if any(value < 0 or value > 100 for value in weights.values()):
        raise ApiError(
            status_code=422,
            code="WEIGHTING_PROFILE_INVALID",
            message="Criterion weights must be between 0 and 100.",
        )


async def _unique_profile_key(session: AsyncSession, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
    stable_key = base
    suffix = 2
    while await session.scalar(
        select(WeightingProfile.id).where(WeightingProfile.stable_key == stable_key).limit(1)
    ):
        stable_key = f"{base}-{suffix}"
        suffix += 1
    return stable_key
