from __future__ import annotations

import asyncio
import hashlib
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

import aiofiles
import httpx
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    Job,
    NodeDefinition,
    WorkflowInputAsset,
    WorkflowInputReference,
    WorkflowNode,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import (
    ProbeResult,
    check_free_space,
    hash_file,
    place_workflow_input,
    probe_media,
    safe_managed_path,
)
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)
from comfy_gallery_core.registry.client import normalize_comfyui_url

INPUT_MEDIA_SEMANTIC_TYPE = "input_media_reference"
CAPTURE_JOB_KIND = "capture_workflow_inputs"
CAPTURE_QUEUE = "workflow"
CAPTURABLE_STATUSES = {"pending", "resolving", "missing", "failed", "unavailable"}
INPUT_FILE_EXTENSIONS = {
    "jpeg",
    "jpg",
    "mov",
    "mp4",
    "png",
    "webm",
    "webp",
}
INPUT_VALUE_NAMES = {
    "file",
    "filename",
    "image",
    "image_file",
    "image_path",
    "video",
    "video_file",
    "video_path",
}
USER_AGENT = "ProjectComfyGallery/0.1 workflow-input-capture"


@dataclass(frozen=True, slots=True)
class WorkflowInputCandidate:
    node_id: UUID
    representation: str
    original_node_id: str
    class_type: str
    locator: str
    input_name: str | None
    media_kind_hint: str | None
    source_filename: str
    source_subfolder: str | None
    source_type: str
    raw_value: object
    discovery_method: str


@dataclass(frozen=True, slots=True)
class WorkflowInputDiscoveryOutcome:
    reference_count: int
    created_count: int
    pending_count: int
    ready_count: int


@dataclass(frozen=True, slots=True)
class WorkflowInputCaptureOutcome:
    reference_count: int
    ready_count: int
    missing_count: int
    failed_count: int
    unsupported_count: int


@dataclass(frozen=True, slots=True)
class CaptureJobReservation:
    job: Job | None
    created: bool


@dataclass(frozen=True, slots=True)
class DownloadedWorkflowInput:
    sha256: str
    byte_size: int
    response_content_type: str | None


class ComfyUIInputClient:
    """Bounded client for ComfyUI's configured input-file endpoint."""

    def __init__(
        self,
        base_url: str,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_comfyui_url(base_url)
        self._maximum_bytes = settings.workflow_input_max_bytes
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(settings.workflow_input_http_timeout_seconds),
            follow_redirects=False,
            headers={
                "Accept": "image/*,video/*",
                "User-Agent": USER_AGENT,
                **(
                    {"comfy-user": settings.comfyui_user}
                    if settings.comfyui_user is not None
                    else {}
                ),
            },
            transport=transport,
        )

    async def __aenter__(self) -> ComfyUIInputClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def download_input(
        self,
        reference: WorkflowInputReference,
        destination: Path,
    ) -> DownloadedWorkflowInput:
        params = {
            "filename": reference.source_filename,
            "type": "input",
        }
        if reference.source_subfolder:
            params["subfolder"] = reference.source_subfolder
        await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(destination.unlink, missing_ok=True)
        try:
            async with self._client.stream("GET", "/view", params=params) as response:
                if response.status_code == 404:
                    raise IngestionError(
                        code="WORKFLOW_INPUT_NOT_FOUND",
                        message="ComfyUI no longer has this workflow input file.",
                        retryable=True,
                    )
                if 300 <= response.status_code < 400:
                    raise IngestionError(
                        code="WORKFLOW_INPUT_REDIRECT_REJECTED",
                        message="ComfyUI attempted to redirect the workflow input request.",
                    )
                response.raise_for_status()
                declared_size = _content_length(response.headers.get("Content-Length"))
                if declared_size is not None and declared_size > self._maximum_bytes:
                    raise _too_large_error(declared_size, self._maximum_bytes)
                digest = hashlib.sha256()
                byte_size = 0
                async with aiofiles.open(destination, "xb") as handle:
                    async for chunk in response.aiter_raw():
                        byte_size += len(chunk)
                        if byte_size > self._maximum_bytes:
                            raise _too_large_error(byte_size, self._maximum_bytes)
                        digest.update(chunk)
                        await handle.write(chunk)
                    await handle.flush()
                if byte_size == 0:
                    raise IngestionError(
                        code="WORKFLOW_INPUT_EMPTY",
                        message="ComfyUI returned an empty workflow input file.",
                    )
                return DownloadedWorkflowInput(
                    sha256=digest.hexdigest(),
                    byte_size=byte_size,
                    response_content_type=response.headers.get("Content-Type"),
                )
        except IngestionError:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise
        except httpx.TimeoutException as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise IngestionError(
                code="WORKFLOW_INPUT_TIMEOUT",
                message="ComfyUI did not return the workflow input within the configured timeout.",
                retryable=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise IngestionError(
                code="WORKFLOW_INPUT_HTTP_ERROR",
                message=(
                    "ComfyUI returned HTTP "
                    f"{exc.response.status_code} while resolving a workflow input."
                ),
                retryable=exc.response.status_code >= 500,
                details={"status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise IngestionError(
                code="WORKFLOW_INPUT_COMFYUI_UNAVAILABLE",
                message="ComfyUI could not be reached while resolving a workflow input.",
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc
        except OSError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise IngestionError(
                code="WORKFLOW_INPUT_STAGING_FAILED",
                message="The workflow input could not be written to staging storage.",
                retryable=True,
                details={"reason": str(exc)},
            ) from exc


async def discover_workflow_inputs(
    session: AsyncSession,
    *,
    snapshot_id: UUID,
    settings: Settings,
) -> WorkflowInputDiscoveryOutcome:
    nodes = list(
        await session.scalars(
            select(WorkflowNode)
            .options(
                selectinload(WorkflowNode.values),
                selectinload(WorkflowNode.node_definition).selectinload(NodeDefinition.mappings),
            )
            .where(
                WorkflowNode.snapshot_id == snapshot_id,
                WorkflowNode.representation == "api_prompt",
            )
            .order_by(WorkflowNode.ordinal)
        )
    )
    candidates = [candidate for node in nodes for candidate in detect_input_candidates(node)]
    existing = list(
        await session.scalars(
            select(WorkflowInputReference).where(WorkflowInputReference.snapshot_id == snapshot_id)
        )
    )
    by_key = {
        (reference.representation, reference.original_node_id, reference.locator): reference
        for reference in existing
    }
    created_count = 0
    for candidate in candidates:
        key = (
            candidate.representation,
            candidate.original_node_id,
            candidate.locator,
        )
        reference = by_key.get(key)
        if reference is None:
            configured = settings.comfyui_base_url is not None
            reference = WorkflowInputReference(
                snapshot_id=snapshot_id,
                node_id=candidate.node_id,
                representation=candidate.representation,
                original_node_id=candidate.original_node_id,
                class_type=candidate.class_type,
                locator=candidate.locator,
                input_name=candidate.input_name,
                media_kind_hint=candidate.media_kind_hint,
                source_filename=candidate.source_filename,
                source_subfolder=candidate.source_subfolder,
                source_type=candidate.source_type,
                raw_value=candidate.raw_value,
                status="pending" if configured else "unavailable",
                last_error_code=None if configured else "COMFYUI_NOT_CONFIGURED",
                last_error_message=(
                    None
                    if configured
                    else "No ComfyUI URL is configured for workflow input capture."
                ),
                resolution_details={"discovery_method": candidate.discovery_method},
            )
            session.add(reference)
            by_key[key] = reference
            created_count += 1
            continue
        reference.node_id = candidate.node_id
        reference.class_type = candidate.class_type
        reference.input_name = candidate.input_name
        reference.media_kind_hint = candidate.media_kind_hint
        reference.source_filename = candidate.source_filename
        reference.source_subfolder = candidate.source_subfolder
        reference.source_type = candidate.source_type
        reference.raw_value = candidate.raw_value
        reference.resolution_details = {
            **reference.resolution_details,
            "discovery_method": candidate.discovery_method,
        }
        if reference.status == "unavailable" and settings.comfyui_base_url is not None:
            reference.status = "pending"
            reference.last_error_code = None
            reference.last_error_message = None
    await session.commit()
    references = list(by_key.values())
    return WorkflowInputDiscoveryOutcome(
        reference_count=len(references),
        created_count=created_count,
        pending_count=sum(reference.status in CAPTURABLE_STATUSES for reference in references),
        ready_count=sum(reference.status == "ready" for reference in references),
    )


def detect_input_candidates(node: WorkflowNode) -> tuple[WorkflowInputCandidate, ...]:
    if node.representation != "api_prompt":
        return ()
    values_by_locator = {value.locator: value for value in node.values}
    candidates: list[WorkflowInputCandidate] = []
    used_locators: set[str] = set()
    definition = node.node_definition
    if definition is not None:
        for mapping in definition.mappings:
            if mapping.state != "active" or mapping.semantic_type != INPUT_MEDIA_SEMANTIC_TYPE:
                continue
            value = values_by_locator.get(mapping.locator)
            if value is None or value.value_kind == "link":
                continue
            candidate = _candidate_from_value(
                node=node,
                locator=mapping.locator,
                input_name=mapping.input_name or value.input_name,
                raw_value=value.raw_value,
                role=mapping.role,
                discovery_method="node_registry_mapping",
            )
            if candidate is not None:
                candidates.append(candidate)
                used_locators.add(candidate.locator)

    if not _looks_like_input_loader(node):
        return tuple(candidates)
    for value in node.values:
        if value.locator in used_locators or value.value_kind == "link":
            continue
        input_name = (value.input_name or "").strip()
        if input_name.casefold() not in INPUT_VALUE_NAMES:
            continue
        candidate = _candidate_from_value(
            node=node,
            locator=value.locator,
            input_name=input_name or None,
            raw_value=value.raw_value,
            role=None,
            discovery_method="loader_heuristic",
        )
        if candidate is not None:
            candidates.append(candidate)
            used_locators.add(candidate.locator)
    return tuple(candidates)


async def create_capture_job_if_needed(
    session: AsyncSession,
    *,
    media_id: UUID,
    settings: Settings,
) -> CaptureJobReservation:
    if settings.comfyui_base_url is None:
        return CaptureJobReservation(job=None, created=False)
    snapshot_id = await session.scalar(
        select(WorkflowSnapshot.id).where(WorkflowSnapshot.media_id == media_id)
    )
    if snapshot_id is None:
        return CaptureJobReservation(job=None, created=False)
    pending_count = int(
        await session.scalar(
            select(func.count())
            .select_from(WorkflowInputReference)
            .where(
                WorkflowInputReference.snapshot_id == snapshot_id,
                WorkflowInputReference.status.in_(CAPTURABLE_STATUSES),
            )
        )
        or 0
    )
    if pending_count == 0:
        return CaptureJobReservation(job=None, created=False)
    active = await session.scalar(
        select(Job)
        .where(
            Job.kind == CAPTURE_JOB_KIND,
            Job.resource_type == "media",
            Job.resource_id == media_id,
            Job.status.in_({"queued", "running"}),
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )
    if active is not None:
        return CaptureJobReservation(job=active, created=False)
    job = Job(
        kind=CAPTURE_JOB_KIND,
        queue=CAPTURE_QUEUE,
        resource_type="media",
        resource_id=media_id,
        progress_total=pending_count,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return CaptureJobReservation(job=job, created=True)


async def process_workflow_input_job(
    session: AsyncSession,
    *,
    media_id: UUID,
    job_id: UUID,
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> WorkflowInputCaptureOutcome | None:
    job = await load_job(session, job_id)
    if not await begin_job(session, job):
        return None
    attempt = await begin_stage(session, job, "capture_workflow_inputs")
    try:
        outcome = await capture_workflow_inputs_for_media(
            session,
            media_id=media_id,
            settings=settings,
            job=job,
            transport=transport,
        )
        await session.refresh(job)
        if job.status == "cancelled":
            attempt.status = "cancelled"
            attempt.completed_at = datetime.now(UTC)
            await session.commit()
            return outcome
        await complete_stage(session, attempt)
        job.error_details = {
            "ready_count": outcome.ready_count,
            "missing_count": outcome.missing_count,
            "failed_count": outcome.failed_count,
            "unsupported_count": outcome.unsupported_count,
        }
        await succeed_job(session, job)
        return outcome
    except IngestionError as error:
        await fail_stage(session, attempt, error)
        await fail_job(session, job, error)
        raise


async def capture_workflow_inputs_for_media(
    session: AsyncSession,
    *,
    media_id: UUID,
    settings: Settings,
    job: Job | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> WorkflowInputCaptureOutcome:
    base_url = settings.comfyui_base_url
    if base_url is None:
        raise IngestionError(
            code="COMFYUI_NOT_CONFIGURED",
            message="No ComfyUI URL is configured for workflow input capture.",
        )
    snapshot = await session.scalar(
        select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == media_id)
    )
    if snapshot is None:
        raise IngestionError(
            code="WORKFLOW_NOT_EXTRACTED",
            message="Workflow input capture requires extracted workflow evidence.",
        )
    references = list(
        await session.scalars(
            select(WorkflowInputReference)
            .where(
                WorkflowInputReference.snapshot_id == snapshot.id,
                WorkflowInputReference.status.in_(CAPTURABLE_STATUSES),
            )
            .order_by(WorkflowInputReference.created_at, WorkflowInputReference.id)
        )
    )
    if job is not None:
        job.progress_total = len(references)
        job.progress_current = 0
        await session.commit()
    async with ComfyUIInputClient(base_url, settings, transport=transport) as client:
        for index, reference in enumerate(references, start=1):
            if job is not None:
                await session.refresh(job)
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.completed_at = datetime.now(UTC)
                    await session.commit()
                    break
            await _capture_reference(
                session,
                reference=reference,
                client=client,
                settings=settings,
            )
            if job is not None:
                job.progress_current = index
                await session.commit()
    current = list(
        await session.scalars(
            select(WorkflowInputReference).where(WorkflowInputReference.snapshot_id == snapshot.id)
        )
    )
    return WorkflowInputCaptureOutcome(
        reference_count=len(current),
        ready_count=sum(reference.status == "ready" for reference in current),
        missing_count=sum(reference.status == "missing" for reference in current),
        failed_count=sum(reference.status == "failed" for reference in current),
        unsupported_count=sum(reference.status == "unsupported" for reference in current),
    )


async def _capture_reference(
    session: AsyncSession,
    *,
    reference: WorkflowInputReference,
    client: ComfyUIInputClient,
    settings: Settings,
) -> None:
    reference.status = "resolving"
    reference.attempt_count += 1
    reference.last_attempt_at = datetime.now(UTC)
    reference.last_error_code = None
    reference.last_error_message = None
    await session.commit()
    staging = settings.resolved_staging_root / "workflow-inputs" / f"{reference.id}.download"
    try:
        downloaded = await client.download_input(reference, staging)
        await asyncio.to_thread(
            check_free_space,
            settings,
            required_bytes=downloaded.byte_size,
        )
        probe = await asyncio.to_thread(probe_media, staging, settings)
        asset = await _resolve_asset(
            session,
            reference=reference,
            staging=staging,
            downloaded=downloaded,
            probe=probe,
            settings=settings,
        )
        reference.input_asset_id = asset.id
        reference.status = "ready"
        reference.resolved_at = datetime.now(UTC)
        reference.last_error_code = None
        reference.last_error_message = None
        reference.resolution_details = {
            **reference.resolution_details,
            "capture_source": "configured_comfyui_current_input",
            "response_content_type": downloaded.response_content_type,
            "kind_hint_matched": (
                reference.media_kind_hint is None or reference.media_kind_hint == asset.kind
            ),
        }
        await session.commit()
    except IngestionError as error:
        with suppress(OSError):
            await asyncio.to_thread(staging.unlink, missing_ok=True)
        reference.status = _reference_failure_status(error)
        reference.last_error_code = error.code
        reference.last_error_message = error.message
        reference.resolution_details = {
            **reference.resolution_details,
            "last_error_details": error.details,
            "retryable": error.retryable,
        }
        await session.commit()


async def _resolve_asset(
    session: AsyncSession,
    *,
    reference: WorkflowInputReference,
    staging: Path,
    downloaded: DownloadedWorkflowInput,
    probe: ProbeResult,
    settings: Settings,
) -> WorkflowInputAsset:
    asset = await session.scalar(
        select(WorkflowInputAsset).where(WorkflowInputAsset.sha256 == downloaded.sha256)
    )
    if asset is not None:
        managed = safe_managed_path(settings, asset.managed_path)
        if managed.is_file():
            existing_sha, _ = await asyncio.to_thread(
                hash_file,
                managed,
                chunk_bytes=settings.hash_chunk_bytes,
            )
            if existing_sha != asset.sha256:
                raise IngestionError(
                    code="WORKFLOW_INPUT_ASSET_CORRUPT",
                    message="A deduplicated workflow input asset failed its hash check.",
                )
            await asyncio.to_thread(staging.unlink, missing_ok=True)
            return asset

    _destination, managed_path = await asyncio.to_thread(
        place_workflow_input,
        staged_path=staging,
        sha256=downloaded.sha256,
        signature=probe.signature,
        settings=settings,
    )
    if asset is not None:
        asset.managed_path = managed_path
        await session.commit()
        return asset

    candidate = WorkflowInputAsset(
        sha256=downloaded.sha256,
        kind=probe.signature.kind,
        detected_format=probe.signature.detected_format,
        mime_type=probe.signature.mime_type,
        byte_size=downloaded.byte_size,
        original_filename=reference.source_filename,
        original_extension=probe.signature.normalized_extension,
        managed_path=managed_path,
        width=probe.width,
        height=probe.height,
        duration_seconds=probe.duration_seconds,
        frame_rate=probe.frame_rate,
        container=probe.container,
        video_codec=probe.video_codec,
        audio_codec=probe.audio_codec,
        probe_data=probe.raw or {},
    )
    try:
        async with session.begin_nested():
            session.add(candidate)
            await session.flush()
    except IntegrityError:
        resolved_asset: WorkflowInputAsset | None = await session.scalar(
            select(WorkflowInputAsset).where(WorkflowInputAsset.sha256 == downloaded.sha256)
        )
        if resolved_asset is None:
            raise
        return resolved_asset
    return candidate


def _candidate_from_value(
    *,
    node: WorkflowNode,
    locator: str,
    input_name: str | None,
    raw_value: object,
    role: str | None,
    discovery_method: str,
) -> WorkflowInputCandidate | None:
    source = _normalize_source_reference(raw_value)
    if source is None:
        return None
    filename, subfolder, source_type = source
    kind = _media_kind_hint(
        role=role,
        class_type=node.class_type,
        input_name=input_name,
        filename=filename,
    )
    if discovery_method == "loader_heuristic" and kind is None:
        return None
    return WorkflowInputCandidate(
        node_id=node.id,
        representation=node.representation,
        original_node_id=node.original_node_id,
        class_type=node.class_type,
        locator=locator,
        input_name=input_name,
        media_kind_hint=kind,
        source_filename=filename,
        source_subfolder=subfolder,
        source_type=source_type,
        raw_value=raw_value,
        discovery_method=discovery_method,
    )


def _normalize_source_reference(value: object) -> tuple[str, str | None, str] | None:
    source_type = "input"
    raw_filename: object = value
    raw_subfolder: object = None
    if isinstance(value, dict):
        raw_filename = value.get("filename", value.get("name"))
        raw_subfolder = value.get("subfolder")
        raw_type = value.get("type")
        if isinstance(raw_type, str) and raw_type.strip():
            source_type = raw_type.strip().casefold()
    if not isinstance(raw_filename, str):
        return None
    annotated = raw_filename.strip()
    lowered = annotated.casefold()
    for marker in (" [input]", " [output]", " [temp]"):
        if lowered.endswith(marker):
            source_type = marker.strip(" []")
            annotated = annotated[: -len(marker)].rstrip()
            break
    if source_type != "input" or not annotated or "\x00" in annotated or "://" in annotated:
        return None
    if annotated.casefold().startswith("blake3:"):
        if len(annotated) > 1024 or "/" in annotated or "\\" in annotated:
            return None
        return annotated, None, source_type
    combined = annotated.replace("\\", "/")
    if isinstance(raw_subfolder, str) and raw_subfolder.strip():
        combined = f"{raw_subfolder.strip().replace('\\', '/')}/{combined}"
    path = PurePosixPath(combined)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    if any(":" in part for part in path.parts):
        return None
    filename = path.name
    subfolder_path = path.parent.as_posix()
    subfolder = None if subfolder_path in {"", "."} else subfolder_path
    if len(filename) > 1024 or (subfolder is not None and len(subfolder) > 2048):
        return None
    return filename, subfolder, source_type


def _looks_like_input_loader(node: WorkflowNode) -> bool:
    lowered_class = node.class_type.casefold()
    if "load" not in lowered_class:
        return False
    if "image" in lowered_class or "video" in lowered_class:
        return True
    definition = node.node_definition
    if definition is None:
        return False
    outputs = {
        str(output).strip().casefold()
        for output in definition.output_schema
        if isinstance(output, str)
    }
    return bool(outputs & {"image", "mask", "video"})


def _media_kind_hint(
    *,
    role: str | None,
    class_type: str,
    input_name: str | None,
    filename: str,
) -> str | None:
    normalized_role = (role or "").strip().casefold()
    if normalized_role in {"image", "video"}:
        return normalized_role
    lowered_class = class_type.casefold()
    lowered_name = (input_name or "").casefold()
    if "video" in lowered_class or lowered_name.startswith("video"):
        return "video"
    if "image" in lowered_class or lowered_name.startswith("image"):
        return "image"
    extension = PurePosixPath(filename).suffix.casefold().lstrip(".")
    if extension not in INPUT_FILE_EXTENSIONS:
        return None
    return "video" if extension in {"mov", "mp4", "webm"} else "image"


def _content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def _too_large_error(actual_bytes: int, maximum_bytes: int) -> IngestionError:
    return IngestionError(
        code="WORKFLOW_INPUT_TOO_LARGE",
        message="The workflow input exceeds the configured capture size limit.",
        details={"response_bytes": actual_bytes, "maximum_bytes": maximum_bytes},
    )


def _reference_failure_status(error: IngestionError) -> str:
    if error.code == "WORKFLOW_INPUT_NOT_FOUND":
        return "missing"
    if error.code in {
        "MEDIA_UNSUPPORTED_FORMAT",
        "MEDIA_TYPE_MISMATCH",
        "WORKFLOW_INPUT_EMPTY",
        "WORKFLOW_INPUT_TOO_LARGE",
    }:
        return "unsupported"
    return "failed"
