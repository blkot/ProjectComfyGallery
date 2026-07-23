from __future__ import annotations

import base64
import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import ExifTags, Image, UnidentifiedImageError

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import MediaSignature, sniff_media

READER_NAME = "comfy_embedded_metadata"
READER_VERSION = "1.0.0"


@dataclass(frozen=True, slots=True)
class EvidenceIssue:
    code: str
    message: str
    field: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
        }


@dataclass(frozen=True, slots=True)
class EmbeddedWorkflowEvidence:
    reader_name: str
    reader_version: str
    source_carrier: str
    evidence_sha256: str
    raw_metadata: dict[str, object]
    raw_api_prompt_text: str | None
    raw_visual_workflow_text: str | None
    api_prompt: dict[str, object] | None
    visual_workflow: dict[str, object] | None
    api_prompt_status: str
    visual_workflow_status: str
    parse_status: str
    issues: tuple[EvidenceIssue, ...]


def read_embedded_workflow(
    path: Path,
    settings: Settings,
    signature: MediaSignature | None = None,
) -> EmbeddedWorkflowEvidence:
    detected = signature or sniff_media(path)
    if detected.kind == "image":
        carrier, raw_metadata, candidates, carrier_malformed = _read_image_metadata(path)
    else:
        carrier, raw_metadata, candidates, carrier_malformed = _read_video_metadata(
            path,
            settings,
        )

    serialized_metadata = _serialize_json(raw_metadata)
    metadata_bytes = len(serialized_metadata.encode("utf-8"))
    if metadata_bytes > settings.workflow_metadata_max_bytes:
        raise IngestionError(
            code="WORKFLOW_METADATA_TOO_LARGE",
            message="Embedded metadata exceeds the configured workflow evidence limit.",
            details={
                "metadata_bytes": metadata_bytes,
                "maximum_bytes": settings.workflow_metadata_max_bytes,
            },
        )

    api_prompt, api_text, api_status, api_issues = _parse_payload(
        candidates.get("prompt"),
        field="prompt",
        settings=settings,
    )
    visual_workflow, visual_text, visual_status, visual_issues = _parse_payload(
        candidates.get("workflow"),
        field="workflow",
        settings=settings,
    )
    issues = tuple((*api_issues, *visual_issues))
    parse_status = _overall_status(
        api_status,
        visual_status,
        carrier_malformed=carrier_malformed,
    )
    if carrier_malformed:
        issues = (
            *issues,
            EvidenceIssue(
                code="WORKFLOW_CONTAINER_METADATA_MALFORMED",
                message="A likely workflow metadata wrapper is not valid JSON.",
            ),
        )

    return EmbeddedWorkflowEvidence(
        reader_name=READER_NAME,
        reader_version=READER_VERSION,
        source_carrier=carrier,
        evidence_sha256=hashlib.sha256(serialized_metadata.encode("utf-8")).hexdigest(),
        raw_metadata=raw_metadata,
        raw_api_prompt_text=api_text,
        raw_visual_workflow_text=visual_text,
        api_prompt=api_prompt,
        visual_workflow=visual_workflow,
        api_prompt_status=api_status,
        visual_workflow_status=visual_status,
        parse_status=parse_status,
        issues=issues,
    )


def _read_image_metadata(
    path: Path,
) -> tuple[str, dict[str, object], dict[str, object], bool]:
    try:
        with Image.open(path) as image:
            text_source = getattr(image, "text", {})
            text_chunks = (
                {str(key): _json_safe(value) for key, value in text_source.items()}
                if isinstance(text_source, dict)
                else {}
            )
            image_info = {
                str(key): _json_safe(value)
                for key, value in image.info.items()
                if key not in text_chunks
            }
            exif_values: dict[str, object] = {}
            try:
                exif = image.getexif()
                for tag_id, value in exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                    exif_values[str(tag_name)] = _json_safe(_decode_exif_value(value))
            except (AttributeError, OSError, ValueError):
                exif_values = {}
            format_name = (image.format or "image").casefold()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise IngestionError(
            code="WORKFLOW_IMAGE_METADATA_READ_FAILED",
            message="Embedded image metadata could not be read.",
            details={"reason": str(exc)},
        ) from exc

    raw_metadata: dict[str, object] = {
        "text_chunks": text_chunks,
        "image_info": image_info,
        "exif": exif_values,
    }
    merged = {**image_info, **exif_values, **text_chunks}
    candidates, malformed = _discover_candidates(merged)
    carrier = "png_text_chunks" if format_name == "png" else f"{format_name}_metadata"
    return carrier, raw_metadata, candidates, malformed


def _read_video_metadata(
    path: Path,
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object], bool]:
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format_tags",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload: object = json.loads(completed.stdout)
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        raise IngestionError(
            code="WORKFLOW_VIDEO_METADATA_READ_FAILED",
            message="Embedded video metadata could not be read.",
            retryable=isinstance(exc, OSError),
            details={"reason": str(exc)},
        ) from exc

    payload_object = payload if isinstance(payload, dict) else {}
    format_payload = payload_object.get("format")
    format_object = format_payload if isinstance(format_payload, dict) else {}
    tags_payload = format_object.get("tags")
    tags = (
        {str(key): _json_safe(value) for key, value in tags_payload.items()}
        if isinstance(tags_payload, dict)
        else {}
    )
    candidates, malformed = _discover_candidates(tags)
    return "video_format_tags", {"format_tags": tags}, candidates, malformed


def _discover_candidates(metadata: dict[str, object]) -> tuple[dict[str, object], bool]:
    lowered = {key.casefold(): value for key, value in metadata.items()}
    candidates: dict[str, object] = {}
    if "prompt" in lowered:
        candidates["prompt"] = lowered["prompt"]
    if "workflow" in lowered:
        candidates["workflow"] = lowered["workflow"]
    if len(candidates) == 2:
        return candidates, False

    malformed = False
    wrapper_names = (
        "comment",
        "description",
        "usercomment",
        "image description",
        "parameters",
    )
    for name in wrapper_names:
        wrapper = lowered.get(name)
        if wrapper is None:
            continue
        parsed, likely_json = _parse_wrapper(wrapper)
        if parsed is None:
            malformed = malformed or likely_json
            continue
        parsed_lowered = {str(key).casefold(): value for key, value in parsed.items()}
        for field in ("prompt", "workflow"):
            if field not in candidates and field in parsed_lowered:
                candidates[field] = parsed_lowered[field]
        if len(candidates) == 2:
            break
    return candidates, malformed


def _parse_wrapper(value: object) -> tuple[dict[str, object] | None, bool]:
    if isinstance(value, dict):
        return {str(key): child for key, child in value.items()}, True
    if not isinstance(value, str):
        return None, False
    stripped = value.lstrip()
    likely_json = stripped.startswith("{")
    if not likely_json:
        return None, False
    try:
        parsed: object = json.loads(value)
    except (json.JSONDecodeError, RecursionError):
        return None, True
    if not isinstance(parsed, dict):
        return None, True
    return {str(key): child for key, child in parsed.items()}, True


def _parse_payload(
    value: object | None,
    *,
    field: str,
    settings: Settings,
) -> tuple[dict[str, object] | None, str | None, str, tuple[EvidenceIssue, ...]]:
    if value is None:
        return None, None, "absent", ()
    raw_text = value if isinstance(value, str) else _serialize_json(_json_safe(value))
    if len(raw_text.encode("utf-8")) > settings.workflow_metadata_max_bytes:
        return (
            None,
            raw_text,
            "malformed",
            (
                EvidenceIssue(
                    code="WORKFLOW_PAYLOAD_TOO_LARGE",
                    message="The embedded workflow payload exceeds the configured limit.",
                    field=field,
                ),
            ),
        )

    parsed: object = value
    try:
        for _ in range(3):
            if not isinstance(parsed, str):
                break
            parsed = json.loads(parsed)
    except (json.JSONDecodeError, RecursionError) as exc:
        reason = exc.msg if isinstance(exc, json.JSONDecodeError) else "nesting is too deep"
        return (
            None,
            raw_text,
            "malformed",
            (
                EvidenceIssue(
                    code="WORKFLOW_JSON_MALFORMED",
                    message=f"The embedded {field} value is not valid JSON: {reason}.",
                    field=field,
                ),
            ),
        )

    if not isinstance(parsed, dict):
        return (
            None,
            raw_text,
            "malformed",
            (
                EvidenceIssue(
                    code="WORKFLOW_JSON_ROOT_INVALID",
                    message=f"The embedded {field} value must be a JSON object.",
                    field=field,
                ),
            ),
        )
    parsed_object = {str(key): child for key, child in parsed.items()}
    issue = _validate_complexity(parsed_object, field=field, settings=settings)
    if issue is not None:
        return None, raw_text, "malformed", (issue,)
    if field == "prompt" and len(parsed_object) > settings.workflow_max_nodes:
        return (
            None,
            raw_text,
            "malformed",
            (
                EvidenceIssue(
                    code="WORKFLOW_NODE_LIMIT_EXCEEDED",
                    message="The API prompt contains more nodes than the configured limit.",
                    field=field,
                ),
            ),
        )
    visual_nodes = parsed_object.get("nodes")
    if (
        field == "workflow"
        and isinstance(visual_nodes, list)
        and len(visual_nodes) > settings.workflow_max_nodes
    ):
        return (
            None,
            raw_text,
            "malformed",
            (
                EvidenceIssue(
                    code="WORKFLOW_NODE_LIMIT_EXCEEDED",
                    message="The visual workflow contains more nodes than the configured limit.",
                    field=field,
                ),
            ),
        )
    return parsed_object, raw_text, "parsed", ()


def _validate_complexity(
    root: object,
    *,
    field: str,
    settings: Settings,
) -> EvidenceIssue | None:
    stack: list[tuple[object, int]] = [(root, 1)]
    item_count = 0
    while stack:
        value, depth = stack.pop()
        if depth > settings.workflow_json_max_depth:
            return EvidenceIssue(
                code="WORKFLOW_JSON_TOO_DEEP",
                message="Embedded workflow JSON exceeds the configured nesting limit.",
                field=field,
            )
        item_count += 1
        if item_count > settings.workflow_json_max_items:
            return EvidenceIssue(
                code="WORKFLOW_JSON_TOO_COMPLEX",
                message="Embedded workflow JSON exceeds the configured item limit.",
                field=field,
            )
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
    return None


def _overall_status(
    api_status: str,
    visual_status: str,
    *,
    carrier_malformed: bool,
) -> str:
    statuses = {api_status, visual_status}
    if "parsed" in statuses and "malformed" in statuses:
        return "partial"
    if "parsed" in statuses:
        return "parsed"
    if "malformed" in statuses or carrier_malformed:
        return "malformed"
    return "absent"


def _decode_exif_value(value: object) -> object:
    if not isinstance(value, bytes):
        return value
    prefixes = (b"ASCII\x00\x00\x00", b"UNICODE\x00", b"JIS\x00\x00\x00\x00\x00")
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return value.decode(encoding).rstrip("\x00")
        except UnicodeDecodeError:
            continue
    return value


def _json_safe(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return {
            "$encoding": "base64",
            "$value": base64.b64encode(value).decode("ascii"),
        }
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(child) for child in value]
    return str(value)


def _serialize_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
