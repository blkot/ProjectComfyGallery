from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.db.models import (
    ExtractionRun,
    LoraSeries,
    LoraSeriesMember,
    ModelArtifact,
    ModelReference,
    ModelUsage,
    SemanticObservation,
    WorkflowEdge,
    WorkflowNode,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.registry.aliases import confirm_safe_reference_alias_groups

TRAINING_SERIES_PATTERN = re.compile(r"^(?P<series>.+)_(?P<step>\d+)$")
PRECISION_PATTERN = re.compile(r"(?:^|[_\-.])(bf16|fp(?:8|16|32))(?:$|[_\-.])", re.I)
QUANTIZATION_PATTERN = re.compile(
    r"(?:^|[_\-.])((?:q|iq)\d(?:_[a-z0-9]+)?)(?:$|[_\-.])",
    re.I,
)


@dataclass(frozen=True, slots=True)
class ModelImportOutcome:
    artifact_count: int
    hash_verified_count: int
    fallback_count: int
    enriched_count: int


@dataclass(frozen=True, slots=True)
class ModelResolutionOutcome:
    reference_count: int
    resolved_count: int
    ambiguous_count: int
    historical_count: int
    usage_count: int
    series_count: int


@dataclass(frozen=True, slots=True)
class TrainingSeriesIdentity:
    opaque_name: str
    training_step: int


@dataclass(frozen=True, slots=True)
class _ObservationOccurrence:
    observation: SemanticObservation
    snapshot_id: UUID
    node: WorkflowNode | None
    reference: ModelReference


async def import_model_inventory(
    session: AsyncSession,
    *,
    lora_items: list[dict[str, object]],
    checkpoint_items: list[dict[str, object]],
    folder_models: dict[str, list[str]],
    metadata_by_path: dict[str, dict[str, object]],
    enrichment_attempted: bool,
) -> ModelImportOutcome:
    artifacts = list(await session.scalars(select(ModelArtifact)))
    by_hash = {artifact.sha256: artifact for artifact in artifacts if artifact.sha256 is not None}
    by_path = {
        (artifact.artifact_type, _match_key(artifact.file_path)): artifact
        for artifact in artifacts
        if artifact.file_path
    }
    for artifact in artifacts:
        if artifact.provider in {"lora_manager", "comfyui_models"} and not _is_manually_set(
            artifact,
            "availability",
        ):
            artifact.availability = "missing"

    imported: list[ModelArtifact] = []
    fallback_count = 0
    now = datetime.now(UTC)
    for kind, items in (("loras", lora_items), ("checkpoints", checkpoint_items)):
        for item in items:
            artifact_type = _artifact_type(kind, item)
            file_path = _optional_text(item.get("file_path"))
            file_name = _optional_text(item.get("file_name"))
            sha256 = _sha256(item.get("sha256"))
            matched_artifact = by_hash.get(sha256) if sha256 is not None else None
            if matched_artifact is None and file_path:
                matched_artifact = by_path.get((artifact_type, _match_key(file_path)))
            if matched_artifact is None:
                matched_artifact = ModelArtifact(
                    artifact_type=artifact_type,
                    display_name=_display_name(item),
                    file_name=file_name,
                    file_path=file_path,
                    sha256=sha256,
                    provider="lora_manager",
                    identity_state="hash_verified" if sha256 else "registry_known",
                    availability="present",
                    enrichment_state="not_attempted",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(matched_artifact)
                artifacts.append(matched_artifact)
                if sha256:
                    by_hash[sha256] = matched_artifact
                if file_path:
                    by_path[(artifact_type, _match_key(file_path))] = matched_artifact
            _apply_inventory_item(
                matched_artifact,
                item=item,
                metadata=metadata_by_path.get(file_path or "", {}),
                enrichment_attempted=enrichment_attempted,
                now=now,
            )
            imported.append(matched_artifact)
    await session.flush()

    alias_index = _artifact_alias_index(artifacts)
    for folder, paths in folder_models.items():
        folder_artifact_type = _folder_artifact_type(folder)
        if folder_artifact_type is None:
            continue
        for path in paths:
            normalized_path = normalize_model_reference(path)
            matches: set[UUID] = set()
            for alias in {
                _match_key(normalized_path),
                _match_key(PurePosixPath(normalized_path).name),
            }:
                matches.update(alias_index.get(alias, set()))
            if matches:
                for artifact_id in matches:
                    artifact = next(
                        candidate for candidate in artifacts if candidate.id == artifact_id
                    )
                    if not _is_manually_set(artifact, "availability"):
                        artifact.availability = "present"
                    artifact.last_seen_at = now
                continue
            file_name = PurePosixPath(path.replace("\\", "/")).name
            precision, quantization = _execution_format(file_name)
            artifact = ModelArtifact(
                artifact_type=folder_artifact_type,
                display_name=file_name or path,
                file_name=file_name or None,
                file_path=path,
                provider="comfyui_models",
                identity_state="registry_known",
                availability="present",
                enrichment_state="not_attempted",
                precision=precision,
                quantization=quantization,
                raw_inventory={"folder": folder, "path": path},
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(artifact)
            await session.flush()
            artifacts.append(artifact)
            imported.append(artifact)
            fallback_count += 1
            for alias in _artifact_aliases(artifact):
                alias_index.setdefault(alias, set()).add(artifact.id)
    await session.commit()

    present = [artifact for artifact in artifacts if artifact.availability == "present"]
    return ModelImportOutcome(
        artifact_count=len(present),
        hash_verified_count=sum(artifact.identity_state == "hash_verified" for artifact in present),
        fallback_count=fallback_count,
        enriched_count=sum(artifact.enrichment_state == "matched" for artifact in present),
    )


async def resolve_model_references(
    session: AsyncSession,
    *,
    snapshot_ids: set[UUID] | None = None,
) -> ModelResolutionOutcome:
    observation_query = (
        select(SemanticObservation, ExtractionRun.snapshot_id, WorkflowNode)
        .join(ExtractionRun, SemanticObservation.run_id == ExtractionRun.id)
        .outerjoin(WorkflowNode, SemanticObservation.node_id == WorkflowNode.id)
        .where(
            ExtractionRun.is_current.is_(True),
            SemanticObservation.observation_type.in_({"checkpoint_reference", "lora_reference"}),
        )
    )
    if snapshot_ids is not None:
        observation_query = observation_query.where(ExtractionRun.snapshot_id.in_(snapshot_ids))
    rows = list((await session.execute(observation_query)).all())
    references = list(
        await session.scalars(select(ModelReference).options(selectinload(ModelReference.artifact)))
    )
    reference_by_key = {
        (reference.reference_type, reference.normalized_value): reference
        for reference in references
    }
    reference_by_id = {reference.id: reference for reference in references}
    for reference in references:
        if snapshot_ids is None:
            reference.occurrence_count = 0
    if snapshot_ids:
        previous_counts = (
            await session.execute(
                select(
                    ModelUsage.model_reference_id,
                    func.count(ModelUsage.id),
                )
                .where(ModelUsage.snapshot_id.in_(snapshot_ids))
                .group_by(ModelUsage.model_reference_id)
            )
        ).all()
        for reference_id, count in previous_counts:
            previous_reference = reference_by_id.get(reference_id)
            if previous_reference is not None:
                previous_reference.occurrence_count = max(
                    0,
                    previous_reference.occurrence_count - int(count),
                )

    artifacts = list(await session.scalars(select(ModelArtifact)))
    alias_index = _artifact_alias_index(artifacts)
    occurrences: list[_ObservationOccurrence] = []
    now = datetime.now(UTC)
    for observation, snapshot_id, node in rows:
        if not isinstance(observation.value, str):
            continue
        reference_type = (
            "lora" if observation.observation_type == "lora_reference" else "checkpoint"
        )
        normalized = normalize_model_reference(observation.value)
        key = (reference_type, normalized)
        matched_reference = reference_by_key.get(key)
        if matched_reference is None:
            matched_reference = ModelReference(
                reference_type=reference_type,
                raw_value=observation.value,
                normalized_value=normalized,
                availability="unknown",
                resolution_state="unresolved",
                occurrence_count=0,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(matched_reference)
            await session.flush()
            references.append(matched_reference)
            reference_by_key[key] = matched_reference
            reference_by_id[matched_reference.id] = matched_reference
        matched_reference.occurrence_count += 1
        matched_reference.last_seen_at = now
        if not matched_reference.manual_override:
            _resolve_reference(matched_reference, alias_index, artifacts)
        occurrences.append(
            _ObservationOccurrence(
                observation=observation,
                snapshot_id=snapshot_id,
                node=node,
                reference=matched_reference,
            )
        )
    await session.flush()
    await _resolve_lora_series(session, references)
    usage_count = await _replace_model_usages(
        session,
        occurrences=occurrences,
        snapshot_ids=snapshot_ids,
    )
    await confirm_safe_reference_alias_groups(session)
    await session.commit()
    active_references = [reference for reference in references if reference.occurrence_count > 0]
    return ModelResolutionOutcome(
        reference_count=len(active_references),
        resolved_count=sum(
            reference.resolution_state == "resolved" for reference in active_references
        ),
        ambiguous_count=sum(
            reference.resolution_state == "ambiguous" for reference in active_references
        ),
        historical_count=sum(
            reference.resolution_state == "historical" for reference in active_references
        ),
        usage_count=usage_count,
        series_count=int(await session.scalar(select(func.count(LoraSeries.id))) or 0),
    )


async def link_model_reference(
    session: AsyncSession,
    *,
    reference: ModelReference,
    artifact: ModelArtifact | None,
) -> ModelReference:
    reference.artifact_id = artifact.id if artifact is not None else None
    reference.artifact = artifact
    reference.manual_override = True
    reference.match_method = "manual"
    reference.confidence = 1.0
    reference.candidate_artifact_ids = []
    if artifact is None:
        reference.resolution_state = "historical"
        reference.availability = "missing"
    else:
        reference.resolution_state = "resolved"
        reference.availability = artifact.availability
    await session.commit()
    await session.refresh(reference)
    return reference


async def update_artifact_fields(
    session: AsyncSession,
    *,
    artifact: ModelArtifact,
    values: dict[str, object],
) -> ModelArtifact:
    allowed = {
        "display_name",
        "artifact_type",
        "architecture_family",
        "lineage",
        "variant",
        "precision",
        "quantization",
        "availability",
    }
    overrides = dict(artifact.manual_overrides)
    for key, value in values.items():
        if key not in allowed:
            continue
        if key in {"display_name", "artifact_type", "availability"} and (
            not isinstance(value, str) or not value.strip()
        ):
            raise IngestionError(
                code="MODEL_FIELD_INVALID",
                message=f"Model field {key} cannot be empty.",
            )
        normalized_value = value.strip() if isinstance(value, str) else value
        setattr(artifact, key, normalized_value)
        overrides[key] = normalized_value
    artifact.manual_overrides = overrides
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def update_series_member(
    session: AsyncSession,
    *,
    member: LoraSeriesMember,
    training_step: int,
) -> LoraSeriesMember:
    if training_step < 0:
        raise IngestionError(
            code="LORA_TRAINING_STEP_INVALID",
            message="A LoRA training step cannot be negative.",
        )
    member.training_step = training_step
    member.source = "manual"
    member.correction_state = "corrected"
    await session.commit()
    await session.refresh(member)
    return member


async def merge_lora_series(
    session: AsyncSession,
    *,
    target: LoraSeries,
    sources: list[LoraSeries],
) -> LoraSeries:
    source_ids = {series.id for series in sources if series.id != target.id}
    if not source_ids:
        raise IngestionError(
            code="LORA_SERIES_MERGE_EMPTY",
            message="Select at least one different LoRA series to merge.",
        )

    target_members = list(
        await session.scalars(
            select(LoraSeriesMember).where(LoraSeriesMember.series_id == target.id)
        )
    )
    target_reference_ids = {member.model_reference_id for member in target_members}
    source_members = list(
        await session.scalars(
            select(LoraSeriesMember).where(LoraSeriesMember.series_id.in_(source_ids))
        )
    )
    for member in source_members:
        if member.model_reference_id in target_reference_ids:
            await session.delete(member)
            continue
        member.series_id = target.id
        member.source = "manual"
        member.correction_state = "corrected"
        target_reference_ids.add(member.model_reference_id)

    target.source = "manual"
    target.correction_state = "corrected"
    await session.flush()
    await session.execute(delete(LoraSeries).where(LoraSeries.id.in_(source_ids)))
    await session.commit()
    return target


async def split_lora_series(
    session: AsyncSession,
    *,
    source: LoraSeries,
    member_ids: list[UUID],
    opaque_name: str,
    display_name: str,
) -> LoraSeries:
    opaque_name = opaque_name.strip()
    display_name = display_name.strip()
    if not opaque_name or not display_name:
        raise IngestionError(
            code="LORA_SERIES_NAME_INVALID",
            message="LoRA series names cannot be empty.",
        )
    unique_member_ids = set(member_ids)
    if not unique_member_ids:
        raise IngestionError(
            code="LORA_SERIES_SPLIT_EMPTY",
            message="Select at least one LoRA series member to split.",
        )
    duplicate = await session.scalar(
        select(LoraSeries.id).where(LoraSeries.opaque_name == opaque_name)
    )
    if duplicate is not None:
        raise IngestionError(
            code="LORA_SERIES_NAME_CONFLICT",
            message="A LoRA series with that opaque name already exists.",
        )
    source_members = list(
        await session.scalars(
            select(LoraSeriesMember).where(
                LoraSeriesMember.series_id == source.id,
            )
        )
    )
    members = [member for member in source_members if member.id in unique_member_ids]
    if len(members) != len(unique_member_ids):
        raise IngestionError(
            code="LORA_SERIES_MEMBER_MISMATCH",
            message="One or more selected members do not belong to this LoRA series.",
        )

    new_series = LoraSeries(
        opaque_name=opaque_name,
        display_name=display_name,
        source="manual",
        correction_state="corrected",
    )
    session.add(new_series)
    await session.flush()
    for member in members:
        member.series_id = new_series.id
        member.source = "manual"
        member.correction_state = "corrected"
    if len(members) == len(source_members):
        await session.flush()
        await session.delete(source)
    else:
        source.source = "manual"
        source.correction_state = "corrected"
    await session.commit()
    return new_series


def parse_lora_training_series(raw_reference: str) -> TrainingSeriesIdentity | None:
    normalized_path = raw_reference.replace("\\", "/")
    filename = PurePosixPath(normalized_path).name
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    match = TRAINING_SERIES_PATTERN.fullmatch(stem)
    if match is None:
        return None
    return TrainingSeriesIdentity(
        opaque_name=match.group("series"),
        training_step=int(match.group("step")),
    )


def normalize_model_reference(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value.strip().replace("\\", "/"))
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


async def _resolve_lora_series(
    session: AsyncSession,
    references: list[ModelReference],
) -> None:
    series_records = list(await session.scalars(select(LoraSeries)))
    series_by_name = {series.opaque_name: series for series in series_records}
    existing_members = list(await session.scalars(select(LoraSeriesMember)))
    membership_keys = {(member.series_id, member.model_reference_id) for member in existing_members}
    manually_assigned_reference_ids = {
        member.model_reference_id
        for member in existing_members
        if member.correction_state == "corrected"
    }
    for reference in references:
        if reference.reference_type != "lora" or reference.occurrence_count <= 0:
            continue
        if reference.id in manually_assigned_reference_ids:
            continue
        parsed = parse_lora_training_series(reference.raw_value)
        if parsed is None:
            continue
        series = series_by_name.get(parsed.opaque_name)
        if series is None:
            series = LoraSeries(
                opaque_name=parsed.opaque_name,
                display_name=parsed.opaque_name,
                source="automatic",
            )
            session.add(series)
            await session.flush()
            series_by_name[parsed.opaque_name] = series
        key = (series.id, reference.id)
        if key in membership_keys:
            continue
        session.add(
            LoraSeriesMember(
                series_id=series.id,
                model_reference_id=reference.id,
                artifact_id=reference.artifact_id,
                training_step=parsed.training_step,
                source="automatic",
            )
        )
        membership_keys.add(key)
    await session.flush()


async def _replace_model_usages(
    session: AsyncSession,
    *,
    occurrences: list[_ObservationOccurrence],
    snapshot_ids: set[UUID] | None,
) -> int:
    if snapshot_ids is None:
        await session.execute(delete(ModelUsage))
    elif snapshot_ids:
        await session.execute(delete(ModelUsage).where(ModelUsage.snapshot_id.in_(snapshot_ids)))
    by_snapshot: dict[UUID, list[_ObservationOccurrence]] = defaultdict(list)
    for occurrence in occurrences:
        by_snapshot[occurrence.snapshot_id].append(occurrence)
    usage_count = 0
    for snapshot_id, snapshot_occurrences in by_snapshot.items():
        nodes = list(
            await session.scalars(
                select(WorkflowNode).where(WorkflowNode.snapshot_id == snapshot_id)
            )
        )
        edges = list(
            await session.scalars(
                select(WorkflowEdge).where(WorkflowEdge.snapshot_id == snapshot_id)
            )
        )
        classifications = _classify_pipeline(snapshot_occurrences, nodes, edges)
        for order, occurrence in enumerate(
            sorted(
                snapshot_occurrences,
                key=lambda item: item.node.ordinal if item.node is not None else 1_000_000,
            )
        ):
            pattern, slot, confidence, evidence = classifications.get(
                occurrence.observation.id,
                ("unresolved", "unclassified", 0.5, {}),
            )
            session.add(
                ModelUsage(
                    snapshot_id=snapshot_id,
                    node_id=occurrence.observation.node_id,
                    observation_id=occurrence.observation.id,
                    model_reference_id=occurrence.reference.id,
                    artifact_id=occurrence.reference.artifact_id,
                    observation_type=occurrence.observation.observation_type,
                    pipeline_pattern=pattern,
                    slot=slot,
                    usage_order=order,
                    confidence=min(
                        confidence,
                        occurrence.reference.confidence
                        if occurrence.reference.confidence is not None
                        else confidence,
                    ),
                    correction_state=(
                        "corrected" if occurrence.reference.manual_override else "uncorrected"
                    ),
                    evidence={
                        **evidence,
                        "reference_match_method": occurrence.reference.match_method,
                    },
                )
            )
            usage_count += 1
    await session.flush()
    return usage_count


def _classify_pipeline(
    occurrences: list[_ObservationOccurrence],
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> dict[UUID, tuple[str, str, float, dict[str, object]]]:
    result: dict[UUID, tuple[str, str, float, dict[str, object]]] = {}
    checkpoints = [
        occurrence
        for occurrence in occurrences
        if occurrence.observation.observation_type == "checkpoint_reference"
    ]
    loras = [
        occurrence
        for occurrence in occurrences
        if occurrence.observation.observation_type == "lora_reference"
    ]
    architecture = _shared_architecture(checkpoints)
    if len(checkpoints) == 1:
        pattern = "single_pass" if _architecture_contains(architecture, "krea2") else "single_model"
        checkpoint = checkpoints[0]
        result[checkpoint.observation.id] = (
            pattern,
            "single",
            0.94,
            {"method": "single_checkpoint_usage", "architecture_family": architecture},
        )
    elif len(checkpoints) > 1:
        sampler_order = _checkpoint_sampler_order(checkpoints, nodes, edges)
        if len(sampler_order) == len(checkpoints) and len(set(sampler_order.values())) == len(
            checkpoints
        ):
            ordered = sorted(checkpoints, key=lambda item: sampler_order[item.observation.id])
            if _architecture_contains(architecture, "wan22"):
                pattern = "dual_noise" if len(ordered) == 2 else "multi_noise"
                slots = ["high_noise", "low_noise"]
            elif _architecture_contains(architecture, "krea2"):
                pattern = "dual_pass" if len(ordered) == 2 else "multi_pass"
                slots = ["first_pass", "second_pass"]
            else:
                pattern = "sequential_dual" if len(ordered) == 2 else "sequential_multi"
                slots = ["first_pass", "second_pass"]
            for index, checkpoint in enumerate(ordered):
                slot = slots[index] if index < len(slots) else f"pass_{index + 1}"
                result[checkpoint.observation.id] = (
                    pattern,
                    slot,
                    0.9,
                    {
                        "method": "sampler_latent_order",
                        "sampler_order": index,
                        "architecture_family": architecture,
                    },
                )
        else:
            for checkpoint in checkpoints:
                result[checkpoint.observation.id] = (
                    "multi_model_unresolved",
                    "unclassified",
                    0.55,
                    {"method": "multiple_checkpoints_without_unique_sampler_order"},
                )
    inherited_pattern = next(iter(result.values()))[0] if result else "adapter_only_or_unresolved"
    for lora in loras:
        result[lora.observation.id] = (
            inherited_pattern,
            "adapter",
            0.9,
            {"method": "adapter_occurrence"},
        )
    return result


def _checkpoint_sampler_order(
    checkpoints: list[_ObservationOccurrence],
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> dict[UUID, int]:
    api_nodes = {
        node.original_node_id: node for node in nodes if node.representation == "api_prompt"
    }
    outgoing: dict[str, list[WorkflowEdge]] = defaultdict(list)
    for edge in edges:
        if edge.representation == "api_prompt":
            outgoing[edge.source_node_id].append(edge)
    samplers = {node_id for node_id, node in api_nodes.items() if _is_sampler_node(node)}
    sampler_graph: dict[str, set[str]] = defaultdict(set)
    indegree = {sampler: 0 for sampler in samplers}
    for edge in edges:
        if (
            edge.representation == "api_prompt"
            and edge.source_node_id in samplers
            and edge.destination_node_id in samplers
            and edge.destination_input_name in {"latent", "latent_image", "samples"}
            and edge.destination_node_id not in sampler_graph[edge.source_node_id]
        ):
            sampler_graph[edge.source_node_id].add(edge.destination_node_id)
            indegree[edge.destination_node_id] += 1
    queue = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    ordered_samplers: list[str] = []
    while queue:
        current = queue.popleft()
        ordered_samplers.append(current)
        for destination in sorted(sampler_graph[current]):
            indegree[destination] -= 1
            if indegree[destination] == 0:
                queue.append(destination)
    sampler_position = {node_id: index for index, node_id in enumerate(ordered_samplers)}

    result: dict[UUID, int] = {}
    for checkpoint in checkpoints:
        if checkpoint.node is None or checkpoint.node.representation != "api_prompt":
            continue
        reached = _reachable_samplers(
            checkpoint.node.original_node_id,
            api_nodes=api_nodes,
            outgoing=outgoing,
            samplers=samplers,
        )
        positions = [
            sampler_position[node_id] for node_id in reached if node_id in sampler_position
        ]
        if positions:
            result[checkpoint.observation.id] = min(positions)
    return result


def _reachable_samplers(
    start_node_id: str,
    *,
    api_nodes: dict[str, WorkflowNode],
    outgoing: dict[str, list[WorkflowEdge]],
    samplers: set[str],
) -> set[str]:
    reached: set[str] = set()
    visited = {start_node_id}
    queue = deque([start_node_id])
    while queue:
        current = queue.popleft()
        for edge in outgoing.get(current, []):
            destination = edge.destination_node_id
            input_name = (edge.destination_input_name or "").casefold()
            if not _is_model_input(input_name):
                continue
            if destination in samplers:
                reached.add(destination)
                continue
            if destination in api_nodes and destination not in visited:
                visited.add(destination)
                queue.append(destination)
    return reached


def _is_sampler_node(node: WorkflowNode) -> bool:
    lowered = node.class_type.casefold()
    if "sampler" in lowered and "sampling" not in lowered:
        return True
    if not isinstance(node.raw_inputs, dict):
        return False
    names = set(node.raw_inputs)
    return "model" in names and (
        "steps" in names or {"positive", "negative", "latent_image"} <= names
    )


def _is_model_input(value: str) -> bool:
    return value == "model" or value.endswith("_model") or value.startswith("model_")


def _shared_architecture(checkpoints: list[_ObservationOccurrence]) -> str | None:
    values: set[str] = set()
    for occurrence in checkpoints:
        architecture = (
            occurrence.reference.artifact.architecture_family
            if occurrence.reference.artifact is not None
            else None
        ) or _infer_architecture_from_identity(occurrence.reference.raw_value)
        if architecture:
            values.add(architecture)
    return next(iter(values)) if len(values) == 1 else None


def _architecture_contains(value: str | None, expected: str) -> bool:
    if value is None:
        return False
    normalized = re.sub(r"[^a-z0-9]+", "", value.casefold())
    if expected == "wan22":
        return "wan" in normalized and "22" in normalized
    return expected in normalized


def _resolve_reference(
    reference: ModelReference,
    alias_index: dict[str, set[UUID]],
    artifacts: list[ModelArtifact],
) -> None:
    keys = {
        _match_key(reference.normalized_value),
        _match_key(PurePosixPath(reference.normalized_value).name),
    }
    candidate_ids: set[UUID] = set()
    for key in keys:
        candidate_ids.update(alias_index.get(key, set()))
    compatible = {
        artifact.id
        for artifact in artifacts
        if artifact.id in candidate_ids
        and _reference_accepts_artifact(reference.reference_type, artifact.artifact_type)
    }
    if len(compatible) == 1:
        artifact_id = next(iter(compatible))
        artifact = next(item for item in artifacts if item.id == artifact_id)
        reference.artifact_id = artifact.id
        reference.artifact = artifact
        reference.availability = artifact.availability
        reference.resolution_state = "resolved"
        reference.match_method = "exact_alias"
        reference.confidence = 0.97
        reference.candidate_artifact_ids = []
    elif len(compatible) > 1:
        reference.artifact_id = None
        reference.availability = "unknown"
        reference.resolution_state = "ambiguous"
        reference.match_method = "multiple_alias_matches"
        reference.confidence = 0.5
        candidate_id_values: list[object] = []
        candidate_id_values.extend(sorted(str(item) for item in compatible))
        reference.candidate_artifact_ids = candidate_id_values
        reference.artifact = None
    else:
        reference.artifact_id = None
        reference.availability = "missing"
        reference.resolution_state = "historical"
        reference.match_method = "workflow_reference_only"
        reference.confidence = 1.0
        reference.candidate_artifact_ids = []
        reference.artifact = None


def _apply_inventory_item(
    artifact: ModelArtifact,
    *,
    item: dict[str, object],
    metadata: dict[str, object],
    enrichment_attempted: bool,
    now: datetime,
) -> None:
    artifact.artifact_type = _preserved_or(
        artifact,
        "artifact_type",
        _artifact_type(
            "loras" if _artifact_type_is_lora(artifact.artifact_type) else "checkpoints",
            item,
        ),
    )
    artifact.display_name = _preserved_or(
        artifact,
        "display_name",
        _display_name(item),
    )
    artifact.file_name = _optional_text(item.get("file_name")) or artifact.file_name
    artifact.file_path = _optional_text(item.get("file_path")) or artifact.file_path
    artifact.sha256 = _sha256(item.get("sha256")) or artifact.sha256
    artifact.provider = "lora_manager"
    artifact.identity_state = "hash_verified" if artifact.sha256 else "registry_known"
    artifact.availability = _preserved_or(artifact, "availability", "present")
    provider_metadata = _metadata_payload(metadata)
    from_civitai = bool(item.get("from_civitai")) or bool(provider_metadata)
    if from_civitai:
        enrichment_state = "matched"
    elif enrichment_attempted:
        enrichment_state = "no_match"
    else:
        enrichment_state = "not_attempted"
    artifact.enrichment_state = enrichment_state
    architecture_family = _meaningful_architecture(
        item.get("base_model"),
        provider_metadata,
    ) or _infer_architecture_family(artifact)
    artifact.architecture_family = _preserved_or(
        artifact,
        "architecture_family",
        architecture_family,
    )
    artifact.lineage = _preserved_or(
        artifact,
        "lineage",
        _infer_lineage(
            artifact,
            provider_metadata=provider_metadata,
            architecture_family=architecture_family,
        ),
    )
    precision, quantization = _execution_format(artifact.file_name or artifact.file_path or "")
    artifact.precision = _preserved_or(artifact, "precision", precision)
    artifact.quantization = _preserved_or(artifact, "quantization", quantization)
    artifact.raw_inventory = item
    artifact.raw_provider_metadata = provider_metadata
    artifact.last_seen_at = now
    civitai = item.get("civitai")
    civitai_object = civitai if isinstance(civitai, dict) else {}
    artifact.provider_model_id = _provider_id(
        provider_metadata.get("modelId"),
        civitai_object.get("modelId"),
    )
    artifact.provider_version_id = _provider_id(
        provider_metadata.get("id"),
        civitai_object.get("id"),
    )
    artifact.provider_url = _optional_text(item.get("hf_url")) or _civitai_url(
        artifact.provider_model_id, artifact.provider_version_id
    )


def _artifact_alias_index(
    artifacts: list[ModelArtifact],
) -> dict[str, set[UUID]]:
    result: dict[str, set[UUID]] = defaultdict(set)
    for artifact in artifacts:
        for alias in _artifact_aliases(artifact):
            result[alias].add(artifact.id)
    return result


def _artifact_aliases(artifact: ModelArtifact) -> set[str]:
    result: set[str] = set()
    for value in (artifact.file_path, artifact.file_name, artifact.display_name):
        if not value:
            continue
        normalized = normalize_model_reference(value)
        result.add(_match_key(normalized))
        result.add(_match_key(PurePosixPath(normalized).name))
    return result


def _artifact_type(kind: str, item: dict[str, object]) -> str:
    if kind == "loras":
        return "lora"
    subtype = (_optional_text(item.get("sub_type")) or "").casefold()
    file_name = (_optional_text(item.get("file_name")) or "").casefold()
    if file_name.endswith(".gguf"):
        return "gguf"
    if "diffusion" in subtype or "unet" in subtype:
        return "diffusion_model"
    return "checkpoint"


def _folder_artifact_type(folder: str) -> str | None:
    return {
        "loras": "lora",
        "checkpoints": "checkpoint",
        "diffusion_models": "diffusion_model",
        "unet": "diffusion_model",
    }.get(folder)


def _reference_accepts_artifact(reference_type: str, artifact_type: str) -> bool:
    if reference_type == "lora":
        return artifact_type == "lora"
    return artifact_type in {"checkpoint", "diffusion_model", "gguf"}


def _display_name(item: dict[str, object]) -> str:
    return (
        _optional_text(item.get("model_name"))
        or _optional_text(item.get("file_name"))
        or _optional_text(item.get("file_path"))
        or "Unnamed model"
    )


def _metadata_payload(value: dict[str, object]) -> dict[str, object]:
    metadata = value.get("metadata")
    return (
        {str(key): child for key, child in metadata.items()} if isinstance(metadata, dict) else {}
    )


def _meaningful_architecture(
    raw_base_model: object,
    metadata: dict[str, object],
) -> str | None:
    candidate = _optional_text(metadata.get("baseModel")) or _optional_text(raw_base_model)
    if candidate is None or candidate.casefold() in {"other", "unknown", "none"}:
        return None
    return candidate


def _infer_architecture_family(artifact: ModelArtifact) -> str | None:
    if artifact.artifact_type == "lora":
        return None
    identity = " ".join(
        value for value in (artifact.display_name, artifact.file_name, artifact.file_path) if value
    )
    return _infer_architecture_from_identity(identity)


def _infer_architecture_from_identity(identity: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "", identity.casefold())
    if "wan" in normalized and "22" in normalized:
        return "Wan 2.2"
    if "wan" in normalized and "21" in normalized:
        return "Wan 2.1"
    if "krea2" in normalized:
        return "Krea 2"
    return None


def _infer_lineage(
    artifact: ModelArtifact,
    *,
    provider_metadata: dict[str, object],
    architecture_family: str | None,
) -> str | None:
    if architecture_family != "Krea 2" or artifact.artifact_type == "lora":
        return None
    identity = " ".join(
        value
        for value in (
            artifact.display_name,
            artifact.file_name,
            _optional_text(provider_metadata.get("name")),
        )
        if value
    )
    normalized = re.sub(r"[^a-z0-9]+", "", identity.casefold())
    if "raw" in normalized:
        return "Raw"
    provider_model = provider_metadata.get("model")
    provider_model_name = (
        _optional_text(provider_model.get("name")) if isinstance(provider_model, dict) else None
    )
    if "turbo" in normalized and (
        provider_model_name is None
        or re.sub(r"[^a-z0-9]+", "", provider_model_name.casefold()).startswith("krea2turbo")
    ):
        return "Turbo"
    return provider_model_name


def _execution_format(value: str) -> tuple[str | None, str | None]:
    precision_match = PRECISION_PATTERN.search(value)
    quantization_match = QUANTIZATION_PATTERN.search(value)
    return (
        precision_match.group(1).casefold() if precision_match else None,
        quantization_match.group(1).upper() if quantization_match else None,
    )


def _preserved_or[T](
    artifact: ModelArtifact,
    key: str,
    value: T,
) -> T:
    if _is_manually_set(artifact, key):
        return cast(T, getattr(artifact, key))
    return value


def _is_manually_set(artifact: ModelArtifact, key: str) -> bool:
    return key in (artifact.manual_overrides or {})


def _artifact_type_is_lora(value: str) -> bool:
    return value == "lora"


def _provider_id(*values: object) -> str | None:
    for value in values:
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return None


def _civitai_url(model_id: str | None, version_id: str | None) -> str | None:
    if model_id is None:
        return None
    base = f"https://civitai.com/models/{model_id}"
    return f"{base}?modelVersionId={version_id}" if version_id else base


def _sha256(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        return None
    return normalized


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _match_key(value: str | None) -> str:
    return normalize_model_reference(value or "").casefold()
