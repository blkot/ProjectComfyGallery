"""Interpret connected API inputs without executing workflows or consulting mutable pools."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

from comfy_gallery_core.db.models import WorkflowNode
from comfy_gallery_core.workflow.graph import EXECUTION_RECORDER_CLASS, dynamic_lm_prompt

CAPTURE_KEY = "comfy_gallery_execution_v1"
LOADER = "Lora Loader (LoraManager)"
STACKER = "Lora Stacker (LoraManager)"
COMBINER = "Lora Stack Combiner (LoraManager)"
CYCLER = "Lora Cycler (LoraManager)"
Output = tuple[str, int]


@dataclass(frozen=True, slots=True)
class DynamicField:
    node: WorkflowNode
    input_name: str
    semantic_type: str
    role: str | None
    value: object
    method: str
    wire: Output | None = None


def _link(value: object) -> Output | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and type(value[0]) in (int, str)
        and type(value[1]) is int
        and value[1] >= 0
    ):
        return str(value[0]), value[1]
    return None


def _input(node: WorkflowNode, name: str) -> object:
    return node.raw_inputs.get(name) if isinstance(node.raw_inputs, dict) else None


def _recorded_outputs(
    nodes: dict[str, WorkflowNode], raw_metadata: dict[str, object]
) -> dict[tuple[Output, str], object]:
    chunks = raw_metadata.get("text_chunks")
    encoded = chunks.get(CAPTURE_KEY) if isinstance(chunks, dict) else None
    if not isinstance(encoded, str):
        return {}
    try:
        records = json.loads(encoded)
    except (ValueError, RecursionError):
        return {}
    captures: dict[tuple[Output, str], object] = {}
    if not isinstance(records, dict):
        return captures
    for node_id, record in records.items():
        tap = nodes.get(node_id)
        if not tap or tap.class_type != EXECUTION_RECORDER_CLASS or not isinstance(record, dict):
            continue
        for pin, kind in (("positive", "text"), ("negative", "text"), ("stack", "stack")):
            wire = _link(_input(tap, pin))
            if wire is None or wire[0] not in nodes or pin not in record:
                continue
            key = (wire, kind)
            value = record[pin]
            # Conflicting recordings cannot be attributed to a particular image.
            captures[key] = value if key not in captures or captures[key] == value else None
    return captures


def _stack_entries(raw: object) -> list[dict[str, object]] | None:
    if not isinstance(raw, list):
        return None
    entries: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, list) or len(item) != 3:
            return None
        name, strength, clip_strength = item
        if (
            not isinstance(name, str)
            or not name.strip()
            or not all(
                type(v) in (int, float) and (isinstance(v, int) or math.isfinite(v))
                for v in (strength, clip_strength)
            )
        ):
            return None
        entries.append(
            {"name": name, "active": True, "strength": strength, "clipStrength": clip_strength}
        )
    return entries


def dynamic_fields(
    workflow_nodes: list[WorkflowNode],
    prompt_roles: dict[UUID, str],
    raw_metadata: dict[str, object],
) -> Iterator[DynamicField]:
    nodes = {n.original_node_id: n for n in workflow_nodes if n.representation == "api_prompt"}
    captures = _recorded_outputs(nodes, raw_metadata)
    consumed = {
        output
        for node in nodes.values()
        if node.class_type != EXECUTION_RECORDER_CLASS and isinstance(node.raw_inputs, dict)
        for value in node.raw_inputs.values()
        if (output := _link(value)) is not None
    }
    stack_wires: list[Output] = []
    for node in nodes.values():
        if node.class_type == LOADER and any(
            (node.original_node_id, slot) in consumed for slot in (0, 1)
        ):
            local = _input(node, "loras")
            if isinstance(local, (list, dict)):
                yield DynamicField(
                    node, "loras", "lora_reference", "adapter", local, "enabled_loader_entries"
                )
            if (wire := _link(_input(node, "lora_stack"))) is not None:
                stack_wires.append(wire)
        if node.class_type == "CLIPTextEncode":
            wire = _link(_input(node, "text"))
            if wire is None or (source := nodes.get(wire[0])) is None:
                continue
            known_dynamic = (
                source.class_type
                in {
                    "StringFunction|pysssss",
                    "XantaPromptLibrary",
                    "Text (LoraManager)",
                }
                or "wildcard" in source.class_type.casefold()
            )
            anchor, locator = node, "text"
        elif node.class_type == "ImpactWildcardEncode" or dynamic_lm_prompt(
            node.class_type, node.raw_inputs
        ):
            # These nodes expose the text they encoded on a separate output.
            wire = (node.original_node_id, 3 if node.class_type == "ImpactWildcardEncode" else 1)
            anchor = source = node
            locator = "populated_text" if node.class_type == "ImpactWildcardEncode" else "text"
            known_dynamic = True
        else:
            continue
        role = prompt_roles.get(anchor.id, "unclassified")
        recorded = captures.get((wire, "text"))
        if isinstance(recorded, str):
            yield DynamicField(anchor, locator, "prompt", role, recorded, "executed_text", wire)
        elif known_dynamic:
            yield DynamicField(
                anchor,
                locator,
                "prompt_unresolved",
                role,
                source.class_type,
                "execution_text_not_recorded",
                wire,
            )

    # A stacker in a disconnected visual graph is not evidence of applied LoRAs.
    visited: set[Output] = set()
    while stack_wires:
        wire = stack_wires.pop()
        if wire in visited or (source := nodes.get(wire[0])) is None:
            continue
        visited.add(wire)
        entries = _stack_entries(captures.get((wire, "stack")))
        if entries is not None:
            yield DynamicField(
                source, "lora_stack", "lora_reference", "adapter", entries, "executed_stack", wire
            )
            continue
        if wire[1] != 0:
            continue
        upstream: tuple[str, ...] = ()
        if source.class_type == COMBINER and isinstance(source.raw_inputs, dict):
            upstream = tuple(
                name for name in source.raw_inputs if re.fullmatch(r"lora_stack(?:\d+|_[ab])", name)
            )
        elif source.class_type == STACKER:
            local = _input(source, "loras")
            if isinstance(local, (list, dict)):
                yield DynamicField(
                    source, "loras", "lora_reference", "adapter", local, "enabled_stack_entries"
                )
            upstream = ("lora_stack",)
        elif source.class_type == CYCLER:
            yield DynamicField(
                source,
                "cycler_config",
                "lora_unresolved",
                "adapter",
                source.class_type,
                "execution_stack_not_recorded",
                wire,
            )
        for name in upstream:
            if (parent := _link(_input(source, name))) is not None:
                stack_wires.append(parent)
