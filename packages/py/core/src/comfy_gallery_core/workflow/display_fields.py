"""Per-output display declarations and scoped recovery; neither changes workflow evidence."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass

DISPLAY_KEY = "comfy_gallery_display_v1"
FIELDS = ("base_model", "lora_list", "character_lora", "prompt", "prompt_id")


def wire(value: object) -> tuple[str, int] | None:
    if (
        isinstance(value, list)
        and len(value) == 2
        and type(value[0]) in (int, str)
        and type(value[1]) is int
        and value[1] >= 0
    ):
        return str(value[0]), value[1]
    return None


def valid_field(name: str, value: object) -> bool:
    if name not in FIELDS:
        return False
    if isinstance(value, str):
        return True
    return (
        name == "lora_list"
        and isinstance(value, list)
        and all(
            isinstance(row, list)
            and len(row) == 3
            and isinstance(row[0], str)
            and row[0].strip()
            and all(type(n) is int or (type(n) is float and math.isfinite(n)) for n in row[1:])
            for row in value
        )
    )


@dataclass(frozen=True)
class DisplayValue:
    value: object
    source: str
    node_id: str
    job_id: str | None = None


def saved_fields(
    raw_metadata: Mapping[str, object], api: Mapping[str, object]
) -> dict[str, DisplayValue]:
    chunks = raw_metadata.get("text_chunks")
    raw = chunks.get(DISPLAY_KEY) if isinstance(chunks, dict) else None
    if not isinstance(raw, str):
        return {}
    try:
        packet = json.loads(raw)
    except (ValueError, RecursionError):
        return {}
    if (
        not isinstance(packet, dict)
        or type(packet.get("version")) is not int
        or packet["version"] != 1
    ):
        return {}
    node_id = packet.get("save_node_id")
    node = api.get(node_id) if isinstance(node_id, str) else None
    if not isinstance(node, dict) or node.get("class_type") != "XantaSaveAndUpload":
        return {}
    fields, inputs = packet.get("fields"), node.get("inputs")
    if not isinstance(fields, dict) or not isinstance(inputs, dict):
        return {}
    result = {}
    for key, value in fields.items():
        source = wire(inputs.get(f"cg_{key}"))
        if valid_field(key, value) and source and source[0] in api:
            result[key] = DisplayValue(value, "save_node", str(node_id))
    return result


def topology(api: Mapping[str, object]) -> str:
    """Fail closed on node class/ID, port wiring or the extraction regex changing.

    Do not fingerprint seeds, prompts, UI caches or model choices. A separate workflow UUID
    and an explicit candidate list are still required for matching other media.
    """
    structure = []
    for key, node in sorted(api.items()):
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise ValueError("Malformed API graph: cannot establish workflow identity.")
        inputs = node["inputs"]
        edges = {
            k: source
            for k, v in inputs.items()
            if (source := wire(v)) is not None and source[0] in api
        }
        regex = (
            {
                k: inputs.get(k)
                for k in (
                    "regex_pattern",
                    "group_index",
                    "mode",
                    "dotall",
                    "multiline",
                    "case_insensitive",
                )
            }
            if node.get("class_type") == "RegexExtract"
            else {}
        )
        meta = node.get("_meta")
        title = (
            meta.get("title")
            if isinstance(meta, dict) and node.get("class_type") == "ShowText|pysssss"
            else None
        )
        library = inputs.get("library") if node.get("class_type") == "XantaPromptLibrary" else None
        structure.append((key, node.get("class_type"), edges, regex, title, library))
    return hashlib.sha256(
        json.dumps(structure, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def workflow_uuid(visual: Mapping[str, object] | None) -> str | None:
    from uuid import UUID

    value = (visual or {}).get("id")
    if isinstance(value, str):
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return None


def widget_candidates(
    api: Mapping[str, object], bindings: Mapping[str, str]
) -> dict[str, str | None]:
    values = {}
    for field, node_id in bindings.items():
        node = api.get(node_id)
        if (
            field not in FIELDS
            or not isinstance(node, dict)
            or node.get("class_type") != "ShowText|pysssss"
            or not isinstance(node.get("inputs"), dict)
            or not (link := wire(node["inputs"].get("text")))
            or link[0] not in api
        ):
            raise ValueError(f"Invalid ShowText binding for {field} at node {node_id}.")
        cached = node["inputs"].get("text_0")
        values[field] = cached if isinstance(cached, str) else None
    return values


def read_shows(
    api: Mapping[str, object], outputs: Mapping[str, object], bindings: Mapping[str, str]
) -> dict[str, str]:
    widget_candidates(api, bindings)  # validate the wiring; never promote the cached strings
    values = {}
    for field, node_id in bindings.items():
        output = outputs.get(node_id)
        texts = output.get("text") if isinstance(output, dict) else None
        if not isinstance(texts, list) or len(texts) != 1 or not isinstance(texts[0], str):
            raise ValueError(f"No unambiguous executed text for {field} at node {node_id}.")
        values[field] = texts[0]
    return values
