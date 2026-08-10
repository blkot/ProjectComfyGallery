from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    Job,
    Media,
    MediaVariant,
    SpatialConversionRun,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    succeed_job,
)

TERMINAL_MSS_STATUSES = {"completed", "completed_with_errors", "failed"}
SUCCESSFUL_PUBLISH_STATUSES = {"published", "variant_exists"}
CONVERTIBLE_MEDIA_STATUSES = {"ready", "ready_with_warnings"}


@dataclass(frozen=True, slots=True)
class MssBatch:
    batch_id: str
    status_url: str | None
    queue_position: int | None
    payload: dict[str, object]


class SpatialConversionClient(Protocol):
    async def submit(
        self,
        *,
        source_path: Path,
        filename: str,
        mime_type: str,
        options: Mapping[str, object],
    ) -> MssBatch: ...

    async def status(self, batch_id: str) -> dict[str, object]: ...


class HttpMssClient:
    """Narrow, origin-pinned adapter for the ml-sharp-spatial batch API."""

    def __init__(self, settings: Settings) -> None:
        if not settings.mss_base_url:
            raise IngestionError(
                code="MSS_NOT_CONFIGURED",
                message="The spatial conversion service is not configured.",
            )
        self._base_url = settings.mss_base_url
        self._timeout = settings.mss_http_timeout_seconds
        self._token = settings.mss_api_token.get_secret_value() if settings.mss_api_token else None
        self._converter_name = settings.mss_converter_name
        self._converter_version = settings.mss_converter_version

    def _headers(self) -> dict[str, str]:
        if not self._token:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    async def submit(
        self,
        *,
        source_path: Path,
        filename: str,
        mime_type: str,
        options: Mapping[str, object],
    ) -> MssBatch:
        data: dict[str, str] = {
            "publish_to_gallery": "true",
            "converter_name": self._converter_name,
            "converter_version": self._converter_version,
        }
        for key in ("precision", "spatial_quality", "spatial_preset"):
            value = options.get(key)
            if isinstance(value, str) and value:
                data[key] = value
        try:
            with source_path.open("rb") as source:
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    headers=self._headers(),
                ) as client:
                    response = await client.post(
                        "/spatial/batches",
                        data=data,
                        files={"videos": (filename, source, mime_type)},
                    )
                    response.raise_for_status()
                    payload = response.json()
        except (OSError, httpx.HTTPError, ValueError) as exc:
            raise IngestionError(
                code="MSS_SUBMIT_FAILED",
                message=(
                    "The source video could not be submitted to the spatial conversion service."
                ),
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc
        batch_id = payload.get("batch_id") if isinstance(payload, dict) else None
        if not isinstance(batch_id, str) or not batch_id:
            raise IngestionError(
                code="MSS_RESPONSE_INVALID",
                message="The spatial conversion service returned an invalid batch response.",
                retryable=True,
            )
        return MssBatch(
            batch_id=batch_id,
            status_url=_short_string(payload.get("status_url"), 1024),
            queue_position=_optional_int(payload.get("queue_position")),
            payload=_bounded_payload(payload),
        )

    async def status(self, batch_id: str) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers(),
            ) as client:
                # Deliberately reconstruct this URL. Never follow an arbitrary URL returned by MSS.
                response = await client.get(f"/spatial/batches/{batch_id}")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IngestionError(
                code="MSS_STATUS_FAILED",
                message="The spatial conversion status could not be read.",
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc
        if not isinstance(payload, dict):
            raise IngestionError(
                code="MSS_RESPONSE_INVALID",
                message="The spatial conversion service returned invalid status data.",
                retryable=True,
            )
        return _bounded_payload(payload)


async def process_spatial_conversion(
    session: AsyncSession,
    *,
    run_id: UUID,
    job: Job,
    settings: Settings,
    client: SpatialConversionClient | None = None,
) -> None:
    run = await session.get(SpatialConversionRun, run_id)
    if run is None:
        raise IngestionError(
            code="SPATIAL_CONVERSION_NOT_FOUND",
            message="The spatial conversion request no longer exists.",
        )
    media = await session.scalar(
        select(Media).options(selectinload(Media.asset)).where(Media.id == run.media_id)
    )
    if media is None or media.asset is None:
        raise IngestionError(
            code="MEDIA_NOT_FOUND",
            message="The source media no longer exists.",
        )
    if media.kind != "video" or media.status not in CONVERTIBLE_MEDIA_STATUSES:
        raise IngestionError(
            code="MEDIA_NOT_CONVERTIBLE",
            message="Only ready video media can be converted to spatial video.",
        )
    if not await begin_job(session, job):
        return

    run.started_at = run.started_at or datetime.now(UTC)
    run.error_code = None
    run.error_message = None
    await session.commit()
    current_stage = await begin_stage(session, job, "submit_to_mss")
    try:
        active_client = client or HttpMssClient(settings)
        if run.mss_batch_id is None:
            run.status = "submitting"
            await session.commit()
            path = safe_managed_path(settings, media.asset.managed_path)
            if not path.is_file():
                raise IngestionError(
                    code="MEDIA_FILE_MISSING",
                    message="The original video is missing from managed storage.",
                    retryable=True,
                )
            batch = await active_client.submit(
                source_path=path,
                filename=media.asset.original_filename,
                mime_type=media.mime_type or "application/octet-stream",
                options=run.requested_options,
            )
            run.mss_batch_id = batch.batch_id
            run.mss_status_url = batch.status_url
            run.queue_position = batch.queue_position
            run.response_data = batch.payload
            run.submitted_at = datetime.now(UTC)
        run.status = "processing"
        await session.commit()
        await complete_stage(session, current_stage)

        current_stage = await begin_stage(session, job, "wait_for_mss")
        await _wait_for_mss(session, run=run, job=job, settings=settings, client=active_client)
        await session.refresh(job)
        if job.status == "cancelled":
            current_stage.status = "cancelled"
            current_stage.completed_at = datetime.now(UTC)
            await session.commit()
            return
        await complete_stage(session, current_stage)
        await succeed_job(session, job)
    except IngestionError as error:
        run.status = "failed"
        run.error_code = error.code
        run.error_message = error.message
        run.completed_at = datetime.now(UTC)
        await session.commit()
        await fail_stage(session, current_stage, error)
        await fail_job(session, job, error)
        raise


async def _wait_for_mss(
    session: AsyncSession,
    *,
    run: SpatialConversionRun,
    job: Job,
    settings: Settings,
    client: SpatialConversionClient,
) -> None:
    if not run.mss_batch_id:
        raise IngestionError(
            code="MSS_BATCH_MISSING",
            message="The conversion request has no external batch identifier.",
        )
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.mss_max_poll_seconds
    while loop.time() < deadline:
        await session.refresh(job)
        if job.cancel_requested:
            run.status = "cancelled"
            run.completed_at = datetime.now(UTC)
            job.status = "cancelled"
            job.completed_at = run.completed_at
            await session.commit()
            return
        payload = await client.status(run.mss_batch_id)
        run.response_data = payload
        run.queue_position = _optional_int(payload.get("queue_position"))
        item = _first_file(payload)
        if item:
            run.mss_file_status = _short_string(item.get("status"), 64)
            run.publish_status = _short_string(item.get("publish_status"), 64)
            run.gallery_media_id = _optional_uuid(item.get("gallery_media_id"))
            run.gallery_variant_id = _optional_uuid(item.get("gallery_variant_id"))
        await session.commit()

        mss_status = payload.get("status")
        if isinstance(mss_status, str) and mss_status in TERMINAL_MSS_STATUSES:
            await _finish_terminal_batch(session, run=run, settings=settings)
            return
        await asyncio.sleep(settings.mss_poll_interval_seconds)
    raise IngestionError(
        code="MSS_POLL_TIMEOUT",
        message="The spatial conversion did not finish before the configured timeout.",
        retryable=True,
    )


async def _finish_terminal_batch(
    session: AsyncSession,
    *,
    run: SpatialConversionRun,
    settings: Settings,
) -> None:
    if run.gallery_media_id is not None and run.gallery_media_id != run.media_id:
        raise IngestionError(
            code="MSS_MEDIA_MISMATCH",
            message="MSS published the spatial result to a different media record.",
        )
    if run.publish_status not in SUCCESSFUL_PUBLISH_STATUSES:
        item = _first_file(run.response_data)
        publish_error = _short_string(item.get("publish_error"), 512) if item else None
        raise IngestionError(
            code="MSS_PUBLISH_FAILED",
            message=publish_error or "MSS did not publish a spatial variant to ComfyGallery.",
            retryable=False,
        )

    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.mss_publish_grace_seconds
    while loop.time() < deadline:
        statement = select(MediaVariant).where(
            MediaVariant.media_id == run.media_id,
            MediaVariant.role == "spatial_video",
            MediaVariant.status == "ready",
            MediaVariant.is_active.is_(True),
        )
        if run.gallery_variant_id is not None:
            statement = statement.where(MediaVariant.id == run.gallery_variant_id)
        elif run.publish_status == "published" and run.previous_variant_id is not None:
            statement = statement.where(MediaVariant.id != run.previous_variant_id)
        variant = await session.scalar(statement)
        if variant is not None:
            run.gallery_variant_id = variant.id
            run.gallery_media_id = run.media_id
            run.status = "succeeded"
            run.completed_at = datetime.now(UTC)
            await session.commit()
            return
        await asyncio.sleep(settings.mss_poll_interval_seconds)
        session.expire_all()
    raise IngestionError(
        code="MSS_PUBLISH_NOT_OBSERVED",
        message="MSS reported success, but ComfyGallery did not observe a ready spatial variant.",
        retryable=True,
    )


def _first_file(payload: Mapping[str, object]) -> dict[str, object] | None:
    files = payload.get("files")
    if not isinstance(files, list) or not files or not isinstance(files[0], dict):
        return None
    return _bounded_payload(files[0])


def _optional_uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _short_string(value: object, limit: int) -> str | None:
    return value[:limit] if isinstance(value, str) else None


def _bounded_payload(value: object, *, depth: int = 0) -> dict[str, object]:
    if not isinstance(value, dict) or depth > 4:
        return {}
    result: dict[str, object] = {}
    for key, item in list(value.items())[:100]:
        name = str(key)[:128]
        if isinstance(item, dict):
            result[name] = _bounded_payload(item, depth=depth + 1)
        elif isinstance(item, list):
            bounded: list[object] = []
            for child in item[:100]:
                if isinstance(child, dict):
                    bounded.append(_bounded_payload(child, depth=depth + 1))
                elif isinstance(child, (str, int, float, bool)) or child is None:
                    bounded.append(child[:2048] if isinstance(child, str) else child)
            result[name] = bounded
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[name] = item[:2048] if isinstance(item, str) else item
    return result
