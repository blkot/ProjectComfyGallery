from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    ExtractionRun,
    Media,
    MediaAsset,
    SemanticObservation,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSnapshot,
    WorkflowValue,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)
from comfy_gallery_core.registry.models import resolve_model_references
from comfy_gallery_core.registry.nodes import (
    create_registry_observations,
    resolve_workflow_nodes,
)
from comfy_gallery_core.workflow.evidence import EmbeddedWorkflowEvidence, read_embedded_workflow
from comfy_gallery_core.workflow.graph import (
    EXTRACTOR_NAME,
    EXTRACTOR_VERSION,
    GRAPH_VERSION,
    GraphBundle,
    NodeSpec,
    normalize_workflow_graph,
)


@dataclass(frozen=True, slots=True)
class WorkflowExtractionOutcome:
    snapshot_id: UUID
    parse_status: str
    api_node_count: int
    visual_node_count: int
    edge_count: int
    observation_count: int
    issue_count: int

    @property
    def has_warnings(self) -> bool:
        return self.parse_status in {"partial", "malformed", "failed"}


async def extract_workflow_for_media(
    session: AsyncSession,
    *,
    media_id: UUID,
    settings: Settings,
    source: Path | None = None,
    reason: str = "ingestion",
) -> WorkflowExtractionOutcome:
    media = await session.get(Media, media_id)
    asset = await session.get(MediaAsset, media_id)
    if media is None or asset is None:
        raise IngestionError(
            code="MEDIA_NOT_FOUND",
            message="Workflow extraction references media that no longer exists.",
        )
    original = source or safe_managed_path(settings, asset.managed_path)
    snapshot = await session.scalar(
        select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == media_id)
    )
    if snapshot is not None and snapshot.parse_status == "failed" and not snapshot.raw_metadata:
        await session.delete(snapshot)
        await session.commit()
        snapshot = None
    if snapshot is None:
        snapshot = await _capture_snapshot(
            session,
            media_id=media_id,
            original=original,
            settings=settings,
        )

    run = ExtractionRun(
        snapshot_id=snapshot.id,
        extractor_name=EXTRACTOR_NAME,
        extractor_version=EXTRACTOR_VERSION,
        graph_version=GRAPH_VERSION,
        configuration_hash=await _configuration_hash(session),
        reason=reason[:80],
        status="running",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        graph = await asyncio.to_thread(
            normalize_workflow_graph,
            snapshot.api_prompt,
            snapshot.visual_workflow,
        )
        node_ids = await _ensure_graph(session, snapshot, graph)
        await resolve_workflow_nodes(session, snapshot_ids={snapshot.id})
        for observation in graph.observations:
            session.add(
                SemanticObservation(
                    run_id=run.id,
                    node_id=(
                        node_ids.get(observation.node_key)
                        if observation.node_key is not None
                        else None
                    ),
                    observation_type=observation.observation_type,
                    role=observation.role,
                    value=observation.value,
                    confidence=observation.confidence,
                    evidence=observation.evidence,
                )
            )
        await session.flush()
        registry_observations = await create_registry_observations(
            session,
            run_id=run.id,
            snapshot_id=snapshot.id,
        )
        observation_count = len(graph.observations) + registry_observations.created_count
        await session.execute(
            update(ExtractionRun)
            .where(
                ExtractionRun.snapshot_id == snapshot.id,
                ExtractionRun.id != run.id,
                ExtractionRun.is_current.is_(True),
            )
            .values(is_current=False)
        )
        issue_count = len(_snapshot_issues(snapshot))
        run.status = (
            "completed_with_warnings"
            if snapshot.parse_status in {"partial", "malformed"}
            else "succeeded"
        )
        run.is_current = True
        run.observation_count = observation_count
        run.configuration_hash = await _configuration_hash(session)
        run.completed_at = datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        run.error_details = {}
        await session.commit()
        await resolve_model_references(session, snapshot_ids={snapshot.id})
        return WorkflowExtractionOutcome(
            snapshot_id=snapshot.id,
            parse_status=snapshot.parse_status,
            api_node_count=snapshot.api_node_count,
            visual_node_count=snapshot.visual_node_count,
            edge_count=snapshot.edge_count,
            observation_count=observation_count,
            issue_count=issue_count,
        )
    except Exception as exc:
        await session.rollback()
        extraction_error = (
            exc
            if isinstance(exc, IngestionError)
            else IngestionError(
                code="WORKFLOW_EXTRACTION_FAILED",
                message="The embedded workflow could not be normalized.",
                details={"reason": str(exc)},
            )
        )
        failed_run = await session.get(ExtractionRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.completed_at = datetime.now(UTC)
            failed_run.error_code = extraction_error.code
            failed_run.error_message = extraction_error.message
            failed_run.error_details = {
                **extraction_error.details,
                "retryable": extraction_error.retryable,
            }
            await session.commit()
        if isinstance(exc, IngestionError):
            raise
        raise extraction_error from exc


async def process_workflow_job(
    session: AsyncSession,
    *,
    media_id: UUID,
    job_id: UUID,
    settings: Settings,
) -> WorkflowExtractionOutcome | None:
    job = await load_job(session, job_id)
    if not await begin_job(session, job):
        return None
    attempt = await begin_stage(session, job, "extract_workflow")
    try:
        outcome = await extract_workflow_for_media(
            session,
            media_id=media_id,
            settings=settings,
            reason="manual_reprocess",
        )
        await complete_stage(session, attempt)
        await succeed_job(session, job)
        return outcome
    except IngestionError as error:
        await fail_stage(session, attempt, error)
        await fail_job(session, job, error)
        raise


async def _capture_snapshot(
    session: AsyncSession,
    *,
    media_id: UUID,
    original: Path,
    settings: Settings,
) -> WorkflowSnapshot:
    try:
        evidence = await asyncio.to_thread(read_embedded_workflow, original, settings)
    except IngestionError as error:
        snapshot = WorkflowSnapshot(
            media_id=media_id,
            reader_name="comfy_embedded_metadata",
            reader_version="1.0.0",
            source_carrier="unreadable",
            evidence_sha256=hashlib.sha256(f"{media_id}:{error.code}".encode()).hexdigest(),
            raw_metadata={},
            raw_api_prompt_text=None,
            raw_visual_workflow_text=None,
            api_prompt=None,
            visual_workflow=None,
            api_prompt_status="absent",
            visual_workflow_status="absent",
            parse_status="failed",
            issue_details={
                "issues": [
                    {
                        "code": error.code,
                        "message": error.message,
                        "field": None,
                    }
                ]
            },
            error_code=error.code,
            error_message=error.message,
        )
        session.add(snapshot)
        await session.commit()
        raise

    snapshot = _snapshot_from_evidence(media_id, evidence)
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


def _snapshot_from_evidence(
    media_id: UUID,
    evidence: EmbeddedWorkflowEvidence,
) -> WorkflowSnapshot:
    return WorkflowSnapshot(
        media_id=media_id,
        reader_name=evidence.reader_name,
        reader_version=evidence.reader_version,
        source_carrier=evidence.source_carrier,
        evidence_sha256=evidence.evidence_sha256,
        raw_metadata=evidence.raw_metadata,
        raw_api_prompt_text=evidence.raw_api_prompt_text,
        raw_visual_workflow_text=evidence.raw_visual_workflow_text,
        api_prompt=evidence.api_prompt,
        visual_workflow=evidence.visual_workflow,
        api_prompt_status=evidence.api_prompt_status,
        visual_workflow_status=evidence.visual_workflow_status,
        parse_status=evidence.parse_status,
        issue_details={"issues": [issue.as_dict() for issue in evidence.issues]},
        error_code=None,
        error_message=None,
    )


async def _ensure_graph(
    session: AsyncSession,
    snapshot: WorkflowSnapshot,
    graph: GraphBundle,
) -> dict[tuple[str, str], UUID]:
    if snapshot.graph_version == GRAPH_VERSION:
        existing_nodes = list(
            await session.scalars(
                select(WorkflowNode).where(WorkflowNode.snapshot_id == snapshot.id)
            )
        )
        return {node_key(node): node.id for node in existing_nodes}

    old_node_ids = select(WorkflowNode.id).where(WorkflowNode.snapshot_id == snapshot.id)
    await session.execute(
        update(SemanticObservation)
        .where(SemanticObservation.node_id.in_(old_node_ids))
        .values(node_id=None)
    )
    await session.execute(delete(WorkflowValue).where(WorkflowValue.node_id.in_(old_node_ids)))
    await session.execute(delete(WorkflowEdge).where(WorkflowEdge.snapshot_id == snapshot.id))
    await session.execute(delete(WorkflowNode).where(WorkflowNode.snapshot_id == snapshot.id))

    node_records: list[tuple[NodeSpec, WorkflowNode]] = []
    for node in graph.nodes:
        record = WorkflowNode(
            snapshot_id=snapshot.id,
            representation=node.representation,
            ordinal=node.ordinal,
            original_node_id=node.original_node_id,
            class_type=node.class_type,
            title=node.title,
            module_hint=node.module_hint,
            mode=node.mode,
            raw_properties=node.raw_properties,
            raw_widgets=node.raw_widgets,
            raw_inputs=node.raw_inputs,
        )
        session.add(record)
        node_records.append((node, record))
    await session.flush()

    node_ids: dict[tuple[str, str], UUID] = {}
    for raw_node, record in node_records:
        key = (record.representation, record.original_node_id)
        node_ids[key] = record.id
        for value in raw_node.values:
            session.add(
                WorkflowValue(
                    node_id=record.id,
                    locator=value.locator,
                    input_name=value.input_name,
                    input_index=value.input_index,
                    value_kind=value.value_kind,
                    raw_value=value.raw_value,
                    normalized_text=value.normalized_text,
                )
            )
    for edge in graph.edges:
        session.add(
            WorkflowEdge(
                snapshot_id=snapshot.id,
                representation=edge.representation,
                ordinal=edge.ordinal,
                original_link_id=edge.original_link_id,
                source_node_id=edge.source_node_id,
                source_output_index=edge.source_output_index,
                destination_node_id=edge.destination_node_id,
                destination_input_index=edge.destination_input_index,
                destination_input_name=edge.destination_input_name,
                declared_type=edge.declared_type,
                raw_link=edge.raw_link,
            )
        )
    snapshot.graph_version = GRAPH_VERSION
    snapshot.api_node_count = graph.api_node_count
    snapshot.visual_node_count = graph.visual_node_count
    snapshot.edge_count = len(graph.edges)
    await session.flush()
    return node_ids


def node_key(node: WorkflowNode) -> tuple[str, str]:
    return node.representation, node.original_node_id


def _snapshot_issues(snapshot: WorkflowSnapshot) -> list[object]:
    issues = snapshot.issue_details.get("issues")
    return issues if isinstance(issues, list) else []


async def _configuration_hash(session: AsyncSession) -> str:
    from comfy_gallery_core.db.models import NodeSemanticMapping

    rows = list(
        (
            await session.execute(
                select(
                    NodeSemanticMapping.id,
                    NodeSemanticMapping.semantic_type,
                    NodeSemanticMapping.role,
                    NodeSemanticMapping.state,
                    NodeSemanticMapping.correction_state,
                    NodeSemanticMapping.updated_at,
                ).order_by(NodeSemanticMapping.id)
            )
        ).all()
    )
    raw = f"{EXTRACTOR_NAME}:{EXTRACTOR_VERSION}:{GRAPH_VERSION}:" + repr(rows)
    return hashlib.sha256(raw.encode()).hexdigest()
