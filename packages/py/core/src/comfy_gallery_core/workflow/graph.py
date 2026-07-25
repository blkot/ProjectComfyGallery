from __future__ import annotations

from dataclasses import dataclass, field

GRAPH_VERSION = "generic-graph-v1"
EXTRACTOR_NAME = "builtin_semantics"
EXTRACTOR_VERSION = "2.2.0"

API_REPRESENTATION = "api_prompt"
VISUAL_REPRESENTATION = "visual_workflow"


@dataclass(frozen=True, slots=True)
class ValueSpec:
    locator: str
    input_name: str | None
    input_index: int | None
    value_kind: str
    raw_value: object
    normalized_text: str | None


@dataclass(frozen=True, slots=True)
class NodeSpec:
    representation: str
    ordinal: int
    original_node_id: str
    class_type: str
    title: str | None
    module_hint: str | None
    mode: int | None
    raw_properties: dict[str, object]
    raw_widgets: list[object]
    raw_inputs: dict[str, object] | list[object]
    values: tuple[ValueSpec, ...] = ()

    @property
    def key(self) -> tuple[str, str]:
        return self.representation, self.original_node_id


@dataclass(frozen=True, slots=True)
class EdgeSpec:
    representation: str
    ordinal: int
    original_link_id: str | None
    source_node_id: str
    source_output_index: int | None
    destination_node_id: str
    destination_input_index: int | None
    destination_input_name: str | None
    declared_type: str | None
    raw_link: list[object] | dict[str, object]


@dataclass(frozen=True, slots=True)
class ObservationSpec:
    node_key: tuple[str, str] | None
    observation_type: str
    role: str | None
    value: object
    confidence: float
    evidence: dict[str, object]


@dataclass(slots=True)
class GraphBundle:
    nodes: list[NodeSpec] = field(default_factory=list)
    edges: list[EdgeSpec] = field(default_factory=list)
    observations: list[ObservationSpec] = field(default_factory=list)

    @property
    def api_node_count(self) -> int:
        return sum(node.representation == API_REPRESENTATION for node in self.nodes)

    @property
    def visual_node_count(self) -> int:
        return sum(node.representation == VISUAL_REPRESENTATION for node in self.nodes)


def normalize_workflow_graph(
    api_prompt: dict[str, object] | None,
    visual_workflow: dict[str, object] | None,
) -> GraphBundle:
    bundle = GraphBundle()
    if api_prompt is not None:
        _normalize_api_prompt(api_prompt, bundle)
    if visual_workflow is not None:
        _normalize_visual_workflow(visual_workflow, bundle)
    return bundle


def _normalize_api_prompt(
    api_prompt: dict[str, object],
    bundle: GraphBundle,
) -> None:
    node_ids = {str(node_id) for node_id in api_prompt}
    api_edge_ordinal = 0
    for ordinal, (raw_node_id, raw_node) in enumerate(api_prompt.items()):
        node_id = str(raw_node_id)
        node = raw_node if isinstance(raw_node, dict) else {}
        class_type = _string_or_none(node.get("class_type")) or "unknown"
        raw_inputs = _string_key_dict(node.get("inputs"))
        metadata = _string_key_dict(node.get("_meta"))
        title = _string_or_none(metadata.get("title")) or _string_or_none(node.get("title"))
        properties = {
            str(key): value for key, value in node.items() if key not in {"inputs", "class_type"}
        }
        if not isinstance(raw_node, dict):
            properties["raw_node"] = raw_node

        values: list[ValueSpec] = []
        for input_name, value in raw_inputs.items():
            is_link = _api_link(value, node_ids)
            values.append(
                ValueSpec(
                    locator=f"input:{input_name}",
                    input_name=input_name,
                    input_index=None,
                    value_kind="link" if is_link else _value_kind(value),
                    raw_value=value,
                    normalized_text=None if is_link else _normalized_text(value),
                )
            )
            if is_link:
                link = value if isinstance(value, list) else []
                bundle.edges.append(
                    EdgeSpec(
                        representation=API_REPRESENTATION,
                        ordinal=api_edge_ordinal,
                        original_link_id=None,
                        source_node_id=str(link[0]),
                        source_output_index=_int_or_none(link[1]),
                        destination_node_id=node_id,
                        destination_input_index=None,
                        destination_input_name=input_name,
                        declared_type=None,
                        raw_link=[*link],
                    )
                )
                api_edge_ordinal += 1
            else:
                observation = _builtin_observation(
                    class_type=class_type,
                    node_id=node_id,
                    input_name=input_name,
                    value=value,
                )
                if observation is not None:
                    bundle.observations.append(observation)

        bundle.nodes.append(
            NodeSpec(
                representation=API_REPRESENTATION,
                ordinal=ordinal,
                original_node_id=node_id,
                class_type=class_type,
                title=title,
                module_hint=_string_or_none(metadata.get("node_module")),
                mode=_int_or_none(node.get("mode")),
                raw_properties=properties,
                raw_widgets=[],
                raw_inputs=raw_inputs,
                values=tuple(values),
            )
        )


def _normalize_visual_workflow(
    workflow: dict[str, object],
    bundle: GraphBundle,
) -> None:
    raw_nodes = workflow.get("nodes")
    nodes = raw_nodes if isinstance(raw_nodes, list) else []
    visual_nodes: dict[str, dict[str, object]] = {}
    for ordinal, raw_node in enumerate(nodes):
        node = raw_node if isinstance(raw_node, dict) else {}
        node_id = str(node.get("id", f"ordinal-{ordinal}"))
        visual_nodes[node_id] = {str(key): value for key, value in node.items()}
        properties = _string_key_dict(node.get("properties"))
        raw_widgets_value = node.get("widgets_values")
        raw_widgets = raw_widgets_value if isinstance(raw_widgets_value, list) else []
        raw_inputs_value = node.get("inputs")
        if isinstance(raw_inputs_value, list):
            raw_inputs: dict[str, object] | list[object] = [*raw_inputs_value]
        else:
            raw_inputs = _string_key_dict(raw_inputs_value)
        values = tuple(
            ValueSpec(
                locator=f"widget:{index}",
                input_name=None,
                input_index=index,
                value_kind=_value_kind(value),
                raw_value=value,
                normalized_text=_normalized_text(value),
            )
            for index, value in enumerate(raw_widgets)
        )
        bundle.nodes.append(
            NodeSpec(
                representation=VISUAL_REPRESENTATION,
                ordinal=ordinal,
                original_node_id=node_id,
                class_type=_string_or_none(node.get("type")) or "unknown",
                title=_string_or_none(node.get("title")),
                module_hint=_module_hint(properties),
                mode=_int_or_none(node.get("mode")),
                raw_properties=properties,
                raw_widgets=[*raw_widgets],
                raw_inputs=raw_inputs,
                values=values,
            )
        )

    raw_links = workflow.get("links")
    links = raw_links if isinstance(raw_links, list) else []
    for ordinal, raw_link in enumerate(links):
        edge = _visual_edge(raw_link, ordinal, visual_nodes)
        if edge is not None:
            bundle.edges.append(edge)


def _visual_edge(
    raw_link: object,
    ordinal: int,
    nodes: dict[str, dict[str, object]],
) -> EdgeSpec | None:
    if isinstance(raw_link, list) and len(raw_link) >= 5:
        source_id = str(raw_link[1])
        destination_id = str(raw_link[3])
        destination_index = _int_or_none(raw_link[4])
        return EdgeSpec(
            representation=VISUAL_REPRESENTATION,
            ordinal=ordinal,
            original_link_id=str(raw_link[0]),
            source_node_id=source_id,
            source_output_index=_int_or_none(raw_link[2]),
            destination_node_id=destination_id,
            destination_input_index=destination_index,
            destination_input_name=_visual_input_name(
                nodes.get(destination_id),
                destination_index,
            ),
            declared_type=_string_or_none(raw_link[5]) if len(raw_link) > 5 else None,
            raw_link=[*raw_link],
        )
    if not isinstance(raw_link, dict):
        return None
    link = {str(key): value for key, value in raw_link.items()}
    mapped_source_id = _first_string(link, "origin_id", "source_id", "from_node")
    mapped_destination_id = _first_string(
        link,
        "target_id",
        "destination_id",
        "to_node",
    )
    if mapped_source_id is None or mapped_destination_id is None:
        return None
    destination_index = _first_int(link, "target_slot", "destination_slot", "to_slot")
    return EdgeSpec(
        representation=VISUAL_REPRESENTATION,
        ordinal=ordinal,
        original_link_id=_first_string(link, "id", "link_id"),
        source_node_id=mapped_source_id,
        source_output_index=_first_int(link, "origin_slot", "source_slot", "from_slot"),
        destination_node_id=mapped_destination_id,
        destination_input_index=destination_index,
        destination_input_name=_visual_input_name(
            nodes.get(mapped_destination_id),
            destination_index,
        ),
        declared_type=_first_string(link, "type", "datatype"),
        raw_link=link,
    )


def _visual_input_name(
    node: dict[str, object] | None,
    input_index: int | None,
) -> str | None:
    if node is None or input_index is None:
        return None
    raw_inputs = node.get("inputs")
    if not isinstance(raw_inputs, list) or not 0 <= input_index < len(raw_inputs):
        return None
    item = raw_inputs[input_index]
    if not isinstance(item, dict):
        return None
    return _string_or_none(item.get("name"))


def _builtin_observation(
    *,
    class_type: str,
    node_id: str,
    input_name: str,
    value: object,
) -> ObservationSpec | None:
    lowered_name = input_name.casefold()
    lowered_class = class_type.casefold()
    if lowered_name == "lora_name" and isinstance(value, str):
        return _observation(
            node_id,
            class_type,
            input_name,
            "lora_reference",
            "unclassified",
            value,
            0.99,
        )
    if lowered_name in {"ckpt_name", "unet_name", "diffusion_model_name"} and isinstance(
        value,
        str,
    ):
        return _observation(
            node_id,
            class_type,
            input_name,
            "checkpoint_reference",
            "unclassified",
            value,
            0.99,
        )
    if (
        lowered_name == "model_name"
        and isinstance(value, str)
        and _is_primary_model_loader(lowered_class)
    ):
        return _observation(
            node_id,
            class_type,
            input_name,
            "checkpoint_reference",
            "unclassified",
            value,
            0.92,
        )
    if isinstance(value, str) and (
        lowered_name in {"positive", "negative", "prompt"}
        or (lowered_name == "text" and ("textencode" in lowered_class or "prompt" in lowered_class))
    ):
        role = lowered_name if lowered_name in {"positive", "negative"} else "unclassified"
        return _observation(
            node_id,
            class_type,
            input_name,
            "prompt",
            role,
            value,
            0.9,
        )
    if lowered_name in {
        "seed",
        "noise_seed",
        "steps",
        "cfg",
        "sampler_name",
        "scheduler",
        "denoise",
        "width",
        "height",
    } and isinstance(value, str | int | float | bool):
        return _observation(
            node_id,
            class_type,
            input_name,
            "generation_parameter",
            lowered_name,
            value,
            0.98,
        )
    return None


def _observation(
    node_id: str,
    class_type: str,
    input_name: str,
    observation_type: str,
    role: str,
    value: object,
    confidence: float,
) -> ObservationSpec:
    return ObservationSpec(
        node_key=(API_REPRESENTATION, node_id),
        observation_type=observation_type,
        role=role,
        value=value,
        confidence=confidence,
        evidence={
            "representation": API_REPRESENTATION,
            "node_id": node_id,
            "class_type": class_type,
            "input_name": input_name,
            "method": "named_api_input",
        },
    )


def _is_primary_model_loader(lowered_class: str) -> bool:
    return any(
        marker in lowered_class
        for marker in (
            "ggufloader",
            "unetloader",
            "checkpointloader",
            "diffusionmodelload",
        )
    )


def _api_link(value: object, node_ids: set[str]) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and str(value[0]) in node_ids
        and _int_or_none(value[1]) is not None
    )


def _value_kind(value: object) -> str:
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
        return "list"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def _normalized_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str | int | float):
        return str(value)
    return None


def _string_key_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): child for key, child in value.items()}


def _module_hint(properties: dict[str, object]) -> str | None:
    for key in ("cnr_id", "aux_id", "module", "python_module"):
        value = _string_or_none(properties.get(key))
        if value:
            return value
    return None


def _first_string(value: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        candidate = _string_or_none(value.get(key))
        if candidate is not None:
            return candidate
    return None


def _first_int(value: dict[str, object], *keys: str) -> int | None:
    for key in keys:
        candidate = _int_or_none(value.get(key))
        if candidate is not None:
            return candidate
    return None


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None
