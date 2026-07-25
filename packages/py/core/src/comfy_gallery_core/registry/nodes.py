from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.db.models import (
    NodeDefinition,
    NodeSchemaSnapshot,
    NodeSemanticMapping,
    SemanticObservation,
    WorkflowEdge,
    WorkflowNode,
)
from comfy_gallery_core.media.errors import IngestionError

GENERATION_PARAMETER_NAMES = {
    "seed",
    "noise_seed",
    "steps",
    "cfg",
    "sampler_name",
    "scheduler",
    "denoise",
    "width",
    "height",
}
CHECKPOINT_INPUT_NAMES = {
    "ckpt_name",
    "unet_name",
    "diffusion_model_name",
}
PROMPT_INPUT_NAMES = {"positive", "negative", "prompt"}


@dataclass(frozen=True, slots=True)
class NodeImportOutcome:
    snapshot_id: UUID
    definition_count: int
    new_definition_count: int
    automatic_mapping_count: int


@dataclass(frozen=True, slots=True)
class NodeResolutionOutcome:
    matched_count: int
    historical_count: int
    ambiguous_count: int
    unresolved_count: int


@dataclass(frozen=True, slots=True)
class RegistryObservationOutcome:
    created_count: int


@dataclass(frozen=True, slots=True)
class MappingSuggestion:
    locator: str
    input_name: str | None
    input_index: int | None
    semantic_type: str
    role: str | None
    confidence: float
    state: str
    evidence: dict[str, object]


@dataclass(frozen=True, slots=True)
class MappedObservationValue:
    value: object
    evidence: dict[str, object]


async def import_node_definitions(
    session: AsyncSession,
    *,
    source_url: str,
    comfyui_version: str | None,
    object_info: dict[str, object],
    maximum_definitions: int,
) -> NodeImportOutcome:
    if len(object_info) > maximum_definitions:
        raise IngestionError(
            code="NODE_REGISTRY_LIMIT_EXCEEDED",
            message="ComfyUI returned more node definitions than the configured limit.",
            details={
                "definition_count": len(object_info),
                "maximum_definitions": maximum_definitions,
            },
        )
    canonical_payload = _canonical_json(object_info)
    payload_hash = hashlib.sha256(canonical_payload.encode()).hexdigest()
    snapshot = await session.scalar(
        select(NodeSchemaSnapshot).where(NodeSchemaSnapshot.object_info_sha256 == payload_hash)
    )
    if snapshot is None:
        snapshot = NodeSchemaSnapshot(
            source_url=source_url,
            comfyui_version=comfyui_version,
            object_info_sha256=payload_hash,
            raw_object_info=object_info,
            definition_count=len(object_info),
        )
        session.add(snapshot)
        await session.flush()

    await session.execute(
        update(NodeDefinition)
        .where(NodeDefinition.source_kind == "comfyui")
        .values(is_present=False)
    )
    existing_definitions = list(await session.scalars(select(NodeDefinition)))
    by_variant = {
        (
            definition.class_type,
            definition.python_module,
            definition.schema_fingerprint,
        ): definition
        for definition in existing_definitions
    }
    imported: list[NodeDefinition] = []
    new_definition_count = 0
    now = datetime.now(UTC)
    for class_type, raw_value in object_info.items():
        raw_definition = _string_key_dict(raw_value)
        python_module = _string(raw_definition.get("python_module")) or ""
        fingerprint = node_schema_fingerprint(class_type, raw_definition)
        key = (class_type, python_module, fingerprint)
        definition = by_variant.get(key)
        if definition is None:
            definition = NodeDefinition(
                source_snapshot_id=snapshot.id,
                class_type=class_type,
                python_module=python_module,
                schema_fingerprint=fingerprint,
                source_kind="comfyui",
                display_name=_string(raw_definition.get("display_name")),
                category=_string(raw_definition.get("category")),
                description=_string(raw_definition.get("description")),
                input_schema=_string_key_dict(raw_definition.get("input")),
                output_schema=_object_list(raw_definition.get("output")),
                raw_definition=raw_definition,
                is_present=True,
                last_seen_at=now,
            )
            session.add(definition)
            by_variant[key] = definition
            new_definition_count += 1
        else:
            definition.source_snapshot_id = snapshot.id
            definition.display_name = _string(raw_definition.get("display_name"))
            definition.category = _string(raw_definition.get("category"))
            definition.description = _string(raw_definition.get("description"))
            definition.input_schema = _string_key_dict(raw_definition.get("input"))
            definition.output_schema = _object_list(raw_definition.get("output"))
            definition.raw_definition = raw_definition
            definition.is_present = True
            definition.last_seen_at = now
        imported.append(definition)
    await session.flush()

    mappings = list(await session.scalars(select(NodeSemanticMapping)))
    mapping_by_locator = {
        (mapping.node_definition_id, mapping.locator): mapping for mapping in mappings
    }
    automatic_mapping_count = 0
    for definition in imported:
        for suggestion in suggest_definition_mappings(definition):
            mapping_key = (definition.id, suggestion.locator)
            mapping = mapping_by_locator.get(mapping_key)
            if mapping is None:
                mapping = NodeSemanticMapping(
                    node_definition_id=definition.id,
                    locator=suggestion.locator,
                    input_name=suggestion.input_name,
                    input_index=suggestion.input_index,
                    semantic_type=suggestion.semantic_type,
                    role=suggestion.role,
                    source="automatic",
                    confidence=suggestion.confidence,
                    state=suggestion.state,
                    evidence=suggestion.evidence,
                )
                session.add(mapping)
                mapping_by_locator[mapping_key] = mapping
                automatic_mapping_count += 1
            elif mapping.source == "automatic":
                mapping.semantic_type = suggestion.semantic_type
                mapping.role = suggestion.role
                mapping.confidence = suggestion.confidence
                mapping.state = suggestion.state
                mapping.evidence = suggestion.evidence
        definition.mapping_state = _mapping_state_for_definition(
            definition.id,
            mapping_by_locator,
        )
    await session.commit()
    return NodeImportOutcome(
        snapshot_id=snapshot.id,
        definition_count=len(imported),
        new_definition_count=new_definition_count,
        automatic_mapping_count=automatic_mapping_count,
    )


async def resolve_workflow_nodes(
    session: AsyncSession,
    *,
    snapshot_ids: set[UUID] | None = None,
) -> NodeResolutionOutcome:
    definitions = list(
        await session.scalars(select(NodeDefinition).options(selectinload(NodeDefinition.mappings)))
    )
    by_class: dict[str, list[NodeDefinition]] = defaultdict(list)
    by_variant: dict[tuple[str, str, str], NodeDefinition] = {}
    for definition in definitions:
        by_class[definition.class_type].append(definition)
        by_variant[
            (
                definition.class_type,
                definition.python_module,
                definition.schema_fingerprint,
            )
        ] = definition
        definition.workflow_occurrence_count = 0

    node_query = select(WorkflowNode)
    if snapshot_ids is not None:
        node_query = node_query.where(WorkflowNode.snapshot_id.in_(snapshot_ids))
    nodes = list(await session.scalars(node_query))
    matched_count = 0
    historical_count = 0
    ambiguous_count = 0
    unresolved_count = 0
    for node in nodes:
        candidates = by_class.get(node.class_type, [])
        selected, confidence, ambiguous = _select_definition(node, candidates)
        if selected is None and not ambiguous:
            selected = await _ensure_historical_definition(
                session,
                node=node,
                by_variant=by_variant,
                by_class=by_class,
            )
            confidence = 1.0
            historical_count += 1
        if selected is not None:
            node.node_definition_id = selected.id
            node.definition_match_state = (
                "historical" if selected.source_kind == "workflow" else "matched"
            )
            node.definition_confidence = confidence
            selected.workflow_occurrence_count += 1
            matched_count += 1
        elif ambiguous:
            node.node_definition_id = None
            node.definition_match_state = "ambiguous"
            node.definition_confidence = confidence
            ambiguous_count += 1
        else:
            node.node_definition_id = None
            node.definition_match_state = "unresolved"
            node.definition_confidence = None
            unresolved_count += 1
    await session.commit()
    return NodeResolutionOutcome(
        matched_count=matched_count,
        historical_count=historical_count,
        ambiguous_count=ambiguous_count,
        unresolved_count=unresolved_count,
    )


async def create_registry_observations(
    session: AsyncSession,
    *,
    run_id: UUID,
    snapshot_id: UUID,
) -> RegistryObservationOutcome:
    nodes = list(
        await session.scalars(
            select(WorkflowNode)
            .options(
                selectinload(WorkflowNode.values),
                selectinload(WorkflowNode.node_definition).selectinload(NodeDefinition.mappings),
            )
            .where(WorkflowNode.snapshot_id == snapshot_id)
        )
    )
    edges = list(
        await session.scalars(select(WorkflowEdge).where(WorkflowEdge.snapshot_id == snapshot_id))
    )
    inferred_prompt_roles = _infer_prompt_roles(nodes, edges)
    existing = list(
        await session.scalars(
            select(SemanticObservation).where(SemanticObservation.run_id == run_id)
        )
    )
    existing_by_key = {
        (
            observation.node_id,
            observation.observation_type,
            _canonical_json(observation.value),
        ): observation
        for observation in existing
    }
    created_count = 0
    for node in nodes:
        definition = node.node_definition
        if definition is None:
            continue
        values_by_locator = {value.locator: value for value in node.values}
        for mapping in definition.mappings:
            if mapping.state != "active" or mapping.semantic_type == "ignore":
                continue
            value = values_by_locator.get(mapping.locator)
            if value is None or value.value_kind == "link":
                continue
            role, role_evidence = _resolved_mapping_role(
                mapping=mapping,
                node=node,
                inferred_prompt_roles=inferred_prompt_roles,
            )
            for observation_value in _mapped_observation_values(
                mapping.semantic_type,
                value.raw_value,
            ):
                key = (
                    node.id,
                    mapping.semantic_type,
                    _canonical_json(observation_value.value),
                )
                mapping_evidence = {
                    "mapping_id": str(mapping.id),
                    "mapping_source": mapping.source,
                    "mapping_method": "node_registry_mapping",
                    **role_evidence,
                }
                existing_observation = existing_by_key.get(key)
                if existing_observation is not None:
                    existing_observation.role = role
                    existing_observation.confidence = max(
                        existing_observation.confidence,
                        mapping.confidence,
                    )
                    existing_observation.correction_state = mapping.correction_state
                    existing_observation.evidence = {
                        **existing_observation.evidence,
                        **mapping_evidence,
                        **observation_value.evidence,
                    }
                    continue
                observation = SemanticObservation(
                    run_id=run_id,
                    node_id=node.id,
                    observation_type=mapping.semantic_type,
                    role=role,
                    value=observation_value.value,
                    confidence=mapping.confidence,
                    correction_state=mapping.correction_state,
                    evidence={
                        "representation": node.representation,
                        "node_id": node.original_node_id,
                        "class_type": node.class_type,
                        "locator": mapping.locator,
                        "method": "node_registry_mapping",
                        **mapping_evidence,
                        **observation_value.evidence,
                    },
                )
                session.add(observation)
                existing_by_key[key] = observation
                created_count += 1
    await session.flush()
    return RegistryObservationOutcome(created_count=created_count)


def _resolved_mapping_role(
    *,
    mapping: NodeSemanticMapping,
    node: WorkflowNode,
    inferred_prompt_roles: dict[UUID, str],
) -> tuple[str | None, dict[str, object]]:
    if mapping.semantic_type != "prompt":
        return mapping.role, {}
    explicit_role = (mapping.role or "").strip()
    if explicit_role and explicit_role.casefold() != "unclassified":
        return explicit_role, {"prompt_role_method": "semantic_mapping"}
    inferred_role = inferred_prompt_roles.get(node.id)
    if inferred_role is not None:
        return inferred_role, {"prompt_role_method": "conditioning_graph"}
    return mapping.role, {}


def _infer_prompt_roles(
    nodes: list[WorkflowNode],
    edges: list[WorkflowEdge],
) -> dict[UUID, str]:
    node_ids = {(node.representation, node.original_node_id): node.id for node in nodes}
    incoming: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    pending: deque[tuple[tuple[str, str], str]] = deque()
    for edge in edges:
        source_key = (edge.representation, edge.source_node_id)
        destination_key = (edge.representation, edge.destination_node_id)
        incoming[destination_key].add(source_key)
        input_role = _conditioning_input_role(edge.destination_input_name)
        if input_role is not None:
            pending.append((source_key, input_role))

    roles_by_key: dict[tuple[str, str], set[str]] = defaultdict(set)
    visited: set[tuple[tuple[str, str], str]] = set()
    while pending:
        node_key, role = pending.popleft()
        visit_key = (node_key, role)
        if visit_key in visited:
            continue
        visited.add(visit_key)
        roles_by_key[node_key].add(role)
        pending.extend((source_key, role) for source_key in incoming.get(node_key, set()))

    inferred: dict[UUID, str] = {}
    for node_key, roles in roles_by_key.items():
        node_id = node_ids.get(node_key)
        if node_id is not None and len(roles) == 1:
            inferred[node_id] = next(iter(roles))
    return inferred


def _conditioning_input_role(input_name: str | None) -> str | None:
    normalized = (input_name or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"positive", "positive_prompt"}:
        return "positive"
    if normalized in {"negative", "negative_prompt"}:
        return "negative"
    return None


def _mapped_observation_values(
    semantic_type: str,
    raw_value: object,
) -> tuple[MappedObservationValue, ...]:
    if semantic_type != "lora_reference":
        return (MappedObservationValue(value=raw_value, evidence={}),)

    container = "direct"
    items: object = raw_value
    if isinstance(raw_value, dict):
        for collection_key in ("__value__", "**value**"):
            if collection_key in raw_value:
                container = collection_key
                items = raw_value[collection_key]
                break
    if not isinstance(items, list):
        return (MappedObservationValue(value=raw_value, evidence={}),)

    active_loras: list[MappedObservationValue] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict) or item.get("active") is not True:
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        active_loras.append(
            MappedObservationValue(
                value=name.strip(),
                evidence={
                    "value_method": "active_lora_collection",
                    "collection_container": container,
                    "collection_index": index,
                    "strength": item.get("strength"),
                    "clip_strength": item.get("clipStrength"),
                },
            )
        )
    return tuple(active_loras)


async def set_manual_mapping(
    session: AsyncSession,
    *,
    definition: NodeDefinition,
    locator: str,
    semantic_type: str,
    role: str | None,
) -> NodeSemanticMapping:
    normalized_locator = locator.strip()
    if not normalized_locator:
        raise IngestionError(
            code="NODE_MAPPING_LOCATOR_INVALID",
            message="A node mapping locator is required.",
        )
    if semantic_type not in {
        "checkpoint_reference",
        "lora_reference",
        "prompt",
        "generation_parameter",
        "ignore",
    }:
        raise IngestionError(
            code="NODE_MAPPING_TYPE_INVALID",
            message="The requested node semantic type is not supported.",
        )
    mapping = await session.scalar(
        select(NodeSemanticMapping).where(
            NodeSemanticMapping.node_definition_id == definition.id,
            NodeSemanticMapping.locator == normalized_locator,
        )
    )
    input_name = (
        normalized_locator.removeprefix("input:")
        if normalized_locator.startswith("input:")
        else None
    )
    input_index = _locator_index(normalized_locator)
    if mapping is None:
        mapping = NodeSemanticMapping(
            node_definition_id=definition.id,
            locator=normalized_locator,
            input_name=input_name,
            input_index=input_index,
            semantic_type=semantic_type,
            role=role,
            source="manual",
            confidence=1.0,
            state="active",
            correction_state="corrected",
            evidence={"method": "manual_correction"},
        )
        session.add(mapping)
    else:
        mapping.input_name = input_name
        mapping.input_index = input_index
        mapping.semantic_type = semantic_type
        mapping.role = role
        mapping.source = "manual"
        mapping.confidence = 1.0
        mapping.state = "active"
        mapping.correction_state = "corrected"
        mapping.evidence = {"method": "manual_correction"}
    definition.mapping_state = "manual"
    await session.commit()
    await session.refresh(mapping)
    return mapping


def node_schema_fingerprint(
    class_type: str,
    definition: dict[str, object],
) -> str:
    payload = {
        "class_type": class_type,
        "python_module": _string(definition.get("python_module")) or "",
        "input": _fingerprint_input_schema(definition.get("input")),
        "output": _object_list(definition.get("output")),
        "output_is_list": _object_list(definition.get("output_is_list")),
        "output_node": bool(definition.get("output_node", False)),
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def observed_node_fingerprint(node: WorkflowNode) -> str:
    inputs: dict[str, object]
    if isinstance(node.raw_inputs, dict):
        inputs = {
            str(name): _observed_value_kind(value)
            for name, value in sorted(node.raw_inputs.items())
        }
    else:
        inputs = {"visual_input_count": len(node.raw_inputs)}
    widgets = [_observed_value_kind(value) for value in node.raw_widgets]
    payload = {
        "class_type": node.class_type,
        "module_hint": node.module_hint or "",
        "representation": node.representation,
        "inputs": inputs,
        "widgets": widgets,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def suggest_definition_mappings(
    definition: NodeDefinition,
) -> list[MappingSuggestion]:
    suggestions: list[MappingSuggestion] = []
    outputs = {
        str(value).casefold() for value in definition.output_schema if isinstance(value, str)
    }
    lowered_class = definition.class_type.casefold()
    for section, values in definition.input_schema.items():
        if section not in {"required", "optional", "hidden"} or not isinstance(values, dict):
            continue
        for raw_name in values:
            name = str(raw_name)
            lowered_name = name.casefold()
            classified = _classify_input(lowered_class, lowered_name, outputs)
            if classified is None:
                continue
            semantic_type, role, confidence = classified
            suggestions.append(
                MappingSuggestion(
                    locator=f"input:{name}",
                    input_name=name,
                    input_index=None,
                    semantic_type=semantic_type,
                    role=role,
                    confidence=confidence,
                    state="active" if confidence >= 0.9 else "suggested",
                    evidence={
                        "method": "definition_input_name",
                        "section": section,
                        "input_name": name,
                    },
                )
            )
    return suggestions


async def _ensure_historical_definition(
    session: AsyncSession,
    *,
    node: WorkflowNode,
    by_variant: dict[tuple[str, str, str], NodeDefinition],
    by_class: dict[str, list[NodeDefinition]],
) -> NodeDefinition:
    module = node.module_hint or ""
    fingerprint = observed_node_fingerprint(node)
    key = (node.class_type, module, fingerprint)
    definition = by_variant.get(key)
    if definition is not None:
        return definition
    observed_inputs = (
        {
            str(name): {"observed_kind": _observed_value_kind(value)}
            for name, value in node.raw_inputs.items()
        }
        if isinstance(node.raw_inputs, dict)
        else {}
    )
    definition = NodeDefinition(
        class_type=node.class_type,
        python_module=module,
        schema_fingerprint=fingerprint,
        source_kind="workflow",
        display_name=node.title or node.class_type,
        input_schema={"required": observed_inputs},
        output_schema=[],
        raw_definition={
            "observed_from_workflow": True,
            "representation": node.representation,
            "input_names": list(observed_inputs),
            "widget_count": len(node.raw_widgets),
        },
        is_present=False,
        mapping_state="unknown",
    )
    session.add(definition)
    await session.flush()
    mapping_by_locator: dict[tuple[UUID, str], NodeSemanticMapping] = {}
    for suggestion in suggest_definition_mappings(definition):
        mapping = NodeSemanticMapping(
            node_definition_id=definition.id,
            locator=suggestion.locator,
            input_name=suggestion.input_name,
            input_index=suggestion.input_index,
            semantic_type=suggestion.semantic_type,
            role=suggestion.role,
            source="automatic",
            confidence=suggestion.confidence,
            state=suggestion.state,
            evidence=suggestion.evidence,
        )
        session.add(mapping)
        mapping_by_locator[(definition.id, suggestion.locator)] = mapping
    definition.mapping_state = _mapping_state_for_definition(
        definition.id,
        mapping_by_locator,
    )
    by_variant[key] = definition
    by_class[node.class_type].append(definition)
    return definition


def _select_definition(
    node: WorkflowNode,
    candidates: list[NodeDefinition],
) -> tuple[NodeDefinition | None, float | None, bool]:
    if not candidates:
        return None, None, False
    input_names = set(node.raw_inputs) if isinstance(node.raw_inputs, dict) else set()
    scored: list[tuple[float, NodeDefinition]] = []
    for candidate in candidates:
        known_inputs = _definition_input_names(candidate)
        overlap = len(input_names & known_inputs) / max(1, len(input_names))
        score = 0.62 + min(0.28, overlap * 0.28)
        if candidate.is_present:
            score += 0.05
        if node.module_hint and candidate.python_module:
            if node.module_hint == candidate.python_module:
                score += 0.05
            elif (
                node.module_hint not in candidate.python_module
                and candidate.python_module not in node.module_hint
            ):
                score -= 0.12
        if (
            candidate.source_kind == "workflow"
            and candidate.schema_fingerprint == observed_node_fingerprint(node)
        ):
            score = 1.0
        scored.append((max(0.0, min(score, 1.0)), candidate))
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_score - 0.025:
        return None, best_score, True
    return best, best_score, False


def _definition_input_names(definition: NodeDefinition) -> set[str]:
    names: set[str] = set()
    for section in ("required", "optional", "hidden"):
        values = definition.input_schema.get(section)
        if isinstance(values, dict):
            names.update(str(name) for name in values)
    return names


def _classify_input(
    lowered_class: str,
    lowered_name: str,
    outputs: set[str],
) -> tuple[str, str | None, float] | None:
    if lowered_name == "lora_name":
        return "lora_reference", "adapter", 0.99
    if lowered_name in CHECKPOINT_INPUT_NAMES:
        return "checkpoint_reference", "unclassified", 0.99
    if (
        lowered_name == "model_name"
        and "model" in outputs
        and any(term in lowered_class for term in ("loader", "checkpoint", "unet", "gguf"))
    ):
        return "checkpoint_reference", "unclassified", 0.93
    if lowered_name in PROMPT_INPUT_NAMES:
        role = lowered_name if lowered_name in {"positive", "negative"} else "unclassified"
        return "prompt", role, 0.94
    if lowered_name == "text" and ("textencode" in lowered_class or "prompt" in lowered_class):
        return "prompt", "unclassified", 0.93
    if lowered_name in GENERATION_PARAMETER_NAMES:
        return "generation_parameter", lowered_name, 0.97
    return None


def _mapping_state_for_definition(
    definition_id: UUID,
    mappings: dict[tuple[UUID, str], NodeSemanticMapping],
) -> str:
    relevant = [
        mapping
        for (mapped_definition_id, _locator), mapping in mappings.items()
        if mapped_definition_id == definition_id and mapping.state == "active"
    ]
    if any(mapping.source == "manual" for mapping in relevant):
        return "manual"
    if relevant:
        return "automatic"
    return "unknown"


def _fingerprint_input_schema(value: object) -> dict[str, object]:
    raw_schema = _string_key_dict(value)
    result: dict[str, object] = {}
    for section, raw_inputs in raw_schema.items():
        if not isinstance(raw_inputs, dict):
            continue
        result[section] = {
            str(name): _fingerprint_input_spec(spec) for name, spec in sorted(raw_inputs.items())
        }
    return result


def _fingerprint_input_spec(value: object) -> object:
    if not isinstance(value, list):
        return _observed_value_kind(value)
    normalized: list[object] = []
    for index, item in enumerate(value):
        if index == 0 and isinstance(item, list):
            normalized.append({"kind": "combo"})
        elif isinstance(item, dict):
            normalized.append(
                {
                    str(key): child
                    for key, child in item.items()
                    if str(key) not in {"default", "tooltip"}
                }
            )
        else:
            normalized.append(item)
    return normalized


def _observed_value_kind(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _locator_index(locator: str) -> int | None:
    if not locator.startswith("widget:"):
        return None
    try:
        return int(locator.removeprefix("widget:"))
    except ValueError:
        return None


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _string_key_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): child for key, child in value.items()}


def _object_list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
