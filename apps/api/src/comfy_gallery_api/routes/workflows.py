from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import (
    ExtractionRunResponse,
    JobResponse,
    SemanticObservationResponse,
    WorkflowBulkReprocessRequest,
    WorkflowBulkReprocessResponse,
    WorkflowDetailResponse,
    WorkflowEdgeResponse,
    WorkflowModelUsageResponse,
    WorkflowNodeResponse,
    WorkflowRawEvidenceResponse,
    WorkflowSnapshotResponse,
)
from comfy_gallery_core.db.models import (
    ExtractionRun,
    Job,
    Media,
    ModelUsage,
    SemanticObservation,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSnapshot,
)
from comfy_gallery_core.queue import enqueue_workflow

router = APIRouter(prefix="/api/v1", tags=["workflows"])


@router.get(
    "/media/{media_id}/workflow",
    response_model=WorkflowDetailResponse,
)
async def get_media_workflow(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
    representation: str | None = Query(default=None, pattern="^(api_prompt|visual_workflow)$"),
    node_limit: int = Query(default=250, ge=1, le=2_000),
    node_offset: int = Query(default=0, ge=0),
    edge_limit: int = Query(default=1_000, ge=1, le=5_000),
) -> WorkflowDetailResponse:
    if await session.get(Media, media_id) is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    snapshot = await session.scalar(
        select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == media_id)
    )
    if snapshot is None:
        return WorkflowDetailResponse(
            media_id=media_id,
            status="unprocessed",
            snapshot=None,
            node_limit=node_limit,
            node_offset=node_offset,
            nodes_truncated=False,
            edges_truncated=False,
            raw_url=None,
        )

    node_filters = [WorkflowNode.snapshot_id == snapshot.id]
    edge_filters = [WorkflowEdge.snapshot_id == snapshot.id]
    if representation is not None:
        node_filters.append(WorkflowNode.representation == representation)
        edge_filters.append(WorkflowEdge.representation == representation)
    total_nodes = int(
        await session.scalar(select(func.count()).select_from(WorkflowNode).where(*node_filters))
        or 0
    )
    total_edges = int(
        await session.scalar(select(func.count()).select_from(WorkflowEdge).where(*edge_filters))
        or 0
    )
    nodes = list(
        await session.scalars(
            select(WorkflowNode)
            .options(selectinload(WorkflowNode.values))
            .where(*node_filters)
            .order_by(WorkflowNode.representation, WorkflowNode.ordinal)
            .offset(node_offset)
            .limit(node_limit)
        )
    )
    edges = list(
        await session.scalars(
            select(WorkflowEdge)
            .where(*edge_filters)
            .order_by(WorkflowEdge.representation, WorkflowEdge.ordinal)
            .limit(edge_limit)
        )
    )
    runs = list(
        await session.scalars(
            select(ExtractionRun)
            .where(ExtractionRun.snapshot_id == snapshot.id)
            .order_by(ExtractionRun.started_at.desc())
            .limit(20)
        )
    )
    current_run = await session.scalar(
        select(ExtractionRun)
        .where(
            ExtractionRun.snapshot_id == snapshot.id,
            ExtractionRun.is_current.is_(True),
        )
        .order_by(ExtractionRun.started_at.desc())
        .limit(1)
    )
    observations = (
        list(
            await session.scalars(
                select(SemanticObservation)
                .where(SemanticObservation.run_id == current_run.id)
                .order_by(
                    SemanticObservation.observation_type,
                    SemanticObservation.created_at,
                )
            )
        )
        if current_run is not None
        else []
    )
    model_usages = list(
        await session.scalars(
            select(ModelUsage)
            .options(
                selectinload(ModelUsage.model_reference),
                selectinload(ModelUsage.artifact),
            )
            .where(ModelUsage.snapshot_id == snapshot.id)
            .order_by(ModelUsage.usage_order)
        )
    )
    return WorkflowDetailResponse(
        media_id=media_id,
        status=snapshot.parse_status,
        snapshot=WorkflowSnapshotResponse.model_validate(snapshot),
        nodes=[WorkflowNodeResponse.model_validate(node) for node in nodes],
        edges=[WorkflowEdgeResponse.model_validate(edge) for edge in edges],
        observations=[
            SemanticObservationResponse.model_validate(observation) for observation in observations
        ],
        model_usages=[
            WorkflowModelUsageResponse(
                id=usage.id,
                node_id=usage.node_id,
                model_reference_id=usage.model_reference_id,
                artifact_id=usage.artifact_id,
                observation_type=usage.observation_type,
                raw_reference=usage.model_reference.raw_value,
                artifact_display_name=(
                    usage.artifact.display_name if usage.artifact is not None else None
                ),
                architecture_family=(
                    usage.artifact.architecture_family if usage.artifact is not None else None
                ),
                lineage=usage.artifact.lineage if usage.artifact is not None else None,
                pipeline_pattern=usage.pipeline_pattern,
                slot=usage.slot,
                usage_order=usage.usage_order,
                confidence=usage.confidence,
                correction_state=usage.correction_state,
                evidence=usage.evidence,
            )
            for usage in model_usages
        ],
        runs=[ExtractionRunResponse.model_validate(run) for run in runs],
        node_limit=node_limit,
        node_offset=node_offset,
        nodes_truncated=node_offset + len(nodes) < total_nodes,
        edges_truncated=len(edges) < total_edges,
        raw_url=f"/api/v1/media/{media_id}/workflow/raw",
    )


@router.get(
    "/media/{media_id}/workflow/raw",
    response_model=WorkflowRawEvidenceResponse,
)
async def get_media_workflow_raw(
    media_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> WorkflowRawEvidenceResponse:
    snapshot = await session.scalar(
        select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == media_id)
    )
    if snapshot is None:
        raise ApiError(
            status_code=404,
            code="WORKFLOW_NOT_EXTRACTED",
            message="No workflow evidence has been extracted for this media.",
        )
    return WorkflowRawEvidenceResponse(
        snapshot_id=snapshot.id,
        evidence_sha256=snapshot.evidence_sha256,
        raw_metadata=snapshot.raw_metadata,
        raw_api_prompt_text=snapshot.raw_api_prompt_text,
        raw_visual_workflow_text=snapshot.raw_visual_workflow_text,
        api_prompt=snapshot.api_prompt,
        visual_workflow=snapshot.visual_workflow,
    )


@router.post(
    "/media/{media_id}/workflow/reprocess",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_media_workflow(
    media_id: UUID,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> JobResponse:
    if await session.get(Media, media_id) is None:
        raise ApiError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            message="The media record was not found.",
        )
    active = await _active_workflow_job(session, media_id)
    if active is not None:
        return JobResponse.model_validate(active)
    job = Job(
        kind="extract_workflow",
        queue="workflow",
        resource_type="media",
        resource_id=media_id,
        progress_total=1,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    try:
        enqueue_workflow(media_id=str(media_id), job_id=str(job.id))
    except Exception as exc:
        await _mark_queue_failure(session, job)
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="Workflow extraction could not be queued.",
        ) from exc
    return JobResponse.model_validate(job)


@router.post(
    "/workflows/reprocess",
    response_model=WorkflowBulkReprocessResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_workflows(
    request: WorkflowBulkReprocessRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> WorkflowBulkReprocessResponse:
    media_query = select(Media.id).order_by(Media.created_at)
    if request.mode == "missing":
        media_query = media_query.where(~Media.workflow_snapshot.has())
    media_ids = list(await session.scalars(media_query))
    active_rows = await session.execute(
        select(Job.resource_id, Job.id).where(
            Job.kind == "extract_workflow",
            Job.status.in_({"queued", "running"}),
            Job.resource_id.in_(media_ids),
        )
    )
    active_media_ids = {resource_id for resource_id, _job_id in active_rows}
    jobs = [
        Job(
            kind="extract_workflow",
            queue="workflow",
            resource_type="media",
            resource_id=media_id,
            progress_total=1,
        )
        for media_id in media_ids
        if media_id not in active_media_ids
    ]
    session.add_all(jobs)
    await session.commit()

    queued_ids: list[UUID] = []
    failed_count = 0
    queue_available = True
    for job in jobs:
        if queue_available:
            try:
                enqueue_workflow(media_id=str(job.resource_id), job_id=str(job.id))
                queued_ids.append(job.id)
                continue
            except Exception:
                queue_available = False
        await _mark_queue_failure(session, job)
        failed_count += 1
    return WorkflowBulkReprocessResponse(
        mode=request.mode,
        matched_count=len(media_ids),
        queued_count=len(queued_ids),
        already_active_count=len(active_media_ids),
        queue_failed_count=failed_count,
        job_ids=queued_ids,
    )


async def _active_workflow_job(session: AsyncSession, media_id: UUID) -> Job | None:
    return cast(
        Job | None,
        await session.scalar(
            select(Job)
            .where(
                Job.kind == "extract_workflow",
                Job.resource_id == media_id,
                Job.status.in_({"queued", "running"}),
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        ),
    )


async def _mark_queue_failure(session: AsyncSession, job: Job) -> None:
    job.status = "failed"
    job.error_code = "QUEUE_UNAVAILABLE"
    job.error_message = "Workflow extraction could not be queued."
    job.error_details = {"retryable": True}
    job.completed_at = datetime.now(UTC)
    await session.commit()
