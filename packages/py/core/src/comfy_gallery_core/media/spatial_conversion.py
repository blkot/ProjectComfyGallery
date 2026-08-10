from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import Job, Media, MediaVariant, SpatialConversionRun
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

CONVERTIBLE_MEDIA_STATUSES = {"ready", "ready_with_warnings"}
ACTIVE_CONVERSION_STATUSES = ("queued", "submitting", "processing")


@dataclass(frozen=True, slots=True)
class MssBatch:
    batch_id: str
    status_url: str | None
    queue_position: int | None
    payload: dict[str, object]


class SpatialConversionClient(Protocol):
    async def submit(
        self, *, source_path: Path, filename: str, mime_type: str, options: Mapping[str, object]
    ) -> MssBatch: ...
    async def status(self, batch_id: str) -> dict[str, object]: ...
    async def publish(self, batch_id: str) -> dict[str, object]: ...


class HttpMssClient:
    """Narrow origin-pinned MSS adapter; returned URLs are never followed."""

    def __init__(self, settings: Settings) -> None:
        if not settings.mss_base_url:
            raise IngestionError(
                code="MSS_NOT_CONFIGURED",
                message="The spatial conversion service is not configured.",
            )
        self._base_url, self._timeout = settings.mss_base_url, settings.mss_http_timeout_seconds
        self._token = settings.mss_api_token.get_secret_value() if settings.mss_api_token else None
        self._converter_name, self._converter_version = (
            settings.mss_converter_name,
            settings.mss_converter_version,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def submit(
        self, *, source_path: Path, filename: str, mime_type: str, options: Mapping[str, object]
    ) -> MssBatch:
        data = {
            "publish_to_gallery": "true",
            "cleanup_mode": "delete_all",
            "converter_name": self._converter_name,
            "converter_version": self._converter_version,
        }
        for key in ("source_media_id", "precision", "spatial_quality", "spatial_preset"):
            value = options.get(key)
            if isinstance(value, str) and value:
                data[key] = value
        try:
            with source_path.open("rb") as source:
                async with httpx.AsyncClient(
                    base_url=self._base_url, timeout=self._timeout, headers=self._headers()
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
        return await self._request("get", f"/spatial/batches/{batch_id}", "MSS_STATUS_FAILED")

    async def publish(self, batch_id: str) -> dict[str, object]:
        return await self._request(
            "post", f"/spatial/batches/{batch_id}/publish", "MSS_PUBLISH_RETRY_FAILED"
        )

    async def _request(self, method: str, path: str, error_code: str) -> dict[str, object]:
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url, timeout=self._timeout, headers=self._headers()
            ) as client:
                if method == "post":
                    response = await client.post(path, json={})
                else:
                    response = await client.get(path)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise IngestionError(
                code=error_code,
                message="The spatial conversion service could not be contacted.",
                retryable=True,
                details={"reason": type(exc).__name__},
            ) from exc
        if not isinstance(payload, dict):
            raise IngestionError(
                code="MSS_RESPONSE_INVALID",
                message="The spatial conversion service returned invalid response data.",
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
    """Perform the finite submit command only; MSS owns long-running conversion."""
    run = await session.get(SpatialConversionRun, run_id)
    if run is None:
        raise IngestionError(
            code="SPATIAL_CONVERSION_NOT_FOUND",
            message="The spatial conversion request was not found.",
        )
    if not await begin_job(session, job):
        return
    run.started_at = run.started_at or datetime.now(UTC)
    stage = await begin_stage(session, job, "submit_to_mss")
    try:
        if run.mss_batch_id is None:
            media = await session.scalar(
                select(Media).options(selectinload(Media.asset)).where(Media.id == run.media_id)
            )
            if media is None or media.asset is None:
                raise IngestionError(
                    code="MEDIA_NOT_FOUND", message="The source media no longer exists."
                )
            if media.kind != "video" or media.status not in CONVERTIBLE_MEDIA_STATUSES:
                raise IngestionError(
                    code="MEDIA_NOT_CONVERTIBLE",
                    message="Only ready video media can be converted to spatial video.",
                )
            path = safe_managed_path(settings, media.asset.managed_path)
            if not path.is_file():
                raise IngestionError(
                    code="MEDIA_FILE_MISSING",
                    message="The original video is missing from managed storage.",
                    retryable=True,
                )
            run.status = "submitting"
            await session.commit()
            batch = await (client or HttpMssClient(settings)).submit(
                source_path=path,
                filename=media.asset.original_filename,
                mime_type=media.mime_type or "application/octet-stream",
                options={**run.requested_options, "source_media_id": str(run.media_id)},
            )
            # A crash after MSS acceptance and before this commit is the unavoidable
            # accept-before-commit window until MSS offers a submission command key.
            run.mss_batch_id, run.mss_status_url, run.queue_position = (
                batch.batch_id,
                batch.status_url,
                batch.queue_position,
            )
            run.response_data, run.submitted_at = batch.payload, datetime.now(UTC)
        run.status = "processing"
        run.error_code = run.error_message = None
        run.next_reconciliation_at = datetime.now(UTC)
        await session.commit()
        await complete_stage(session, stage)
        await succeed_job(session, job)
    except IngestionError as error:
        run.status, run.error_code, run.error_message, run.completed_at = (
            "failed",
            error.code,
            error.message,
            datetime.now(UTC),
        )
        await session.commit()
        await fail_stage(session, stage, error)
        await fail_job(session, job, error)
        raise


async def reconcile_spatial_conversion(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings: Settings,
    client: SpatialConversionClient | None = None,
    force: bool = False,
) -> bool:
    """Execute one MSS GET and return whether a later low-frequency reconciliation is needed."""
    run = await session.get(SpatialConversionRun, run_id)
    if run is None or run.status not in ACTIVE_CONVERSION_STATUSES or not run.mss_batch_id:
        return False
    now = datetime.now(UTC)
    claim = update(SpatialConversionRun).where(
        SpatialConversionRun.id == run_id,
        SpatialConversionRun.status.in_(ACTIVE_CONVERSION_STATUSES),
        SpatialConversionRun.mss_batch_id.is_not(None),
    )
    if not force:
        claim = claim.where(
            or_(
                SpatialConversionRun.next_reconciliation_at.is_(None),
                SpatialConversionRun.next_reconciliation_at <= now,
            )
        )
    claimed = await session.execute(
        claim.values(
            next_reconciliation_at=now
            + timedelta(seconds=settings.mss_reconciliation_interval_seconds)
        )
    )
    if not int(getattr(claimed, "rowcount", 0) or 0):
        return False
    await session.commit()
    await session.refresh(run)
    payload = await (client or HttpMssClient(settings)).status(run.mss_batch_id)
    # Validation/activation may complete while the network request is in flight.
    # Re-read under a write lock before applying MSS evidence so a stale status
    # response can never reverse CG's authoritative terminal success.
    current_run: SpatialConversionRun | None = await session.scalar(
        select(SpatialConversionRun)
        .where(SpatialConversionRun.id == run_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if current_run is None or current_run.status not in ACTIVE_CONVERSION_STATUSES:
        await session.commit()
        return False
    run = current_run
    reconciled_at = datetime.now(UTC)
    _apply_mss_status(run, payload)
    run.last_reconciled_at = reconciled_at
    run.next_reconciliation_at = reconciled_at + timedelta(
        seconds=settings.mss_reconciliation_interval_seconds
    )
    if payload.get("status") == "failed" or run.mss_file_status == "failed":
        run.status, run.error_code = "failed", "MSS_GENERATION_FAILED"
        item = _first_file(payload)
        run.error_message = (
            _short_string(item.get("error"), 512) if item else "MSS generation failed."
        )
        run.completed_at = reconciled_at
    elif run.publish_status in {"published", "variant_exists"}:
        await _complete_run_from_ready_variant(session, run=run)
    await session.commit()
    return run.status == "processing"


async def request_spatial_publish_retry(
    session: AsyncSession,
    *,
    run_id: UUID,
    settings: Settings,
    client: SpatialConversionClient | None = None,
) -> None:
    run = await session.get(SpatialConversionRun, run_id)
    if run is None or not run.mss_batch_id:
        raise IngestionError(
            code="MSS_BATCH_MISSING",
            message="The conversion request has no external batch identifier.",
        )
    try:
        payload = await (client or HttpMssClient(settings)).publish(run.mss_batch_id)
    except IngestionError as error:
        run.error_code = error.code
        run.error_message = error.message
        await session.commit()
        raise
    _apply_mss_status(run, payload)
    run.next_reconciliation_at = datetime.now(UTC)
    await session.commit()


async def complete_active_spatial_conversion_from_variant(
    session: AsyncSession, *, variant: MediaVariant
) -> bool:
    """CG validation/activation is the authoritative idempotent success event."""
    if variant.status not in {"ready", "duplicate"}:
        return False
    resolved_id = (
        variant.id
        if variant.status == "ready"
        else _optional_uuid(variant.validation_data.get("duplicate_of_variant_id"))
    )
    if resolved_id is None or (variant.status == "ready" and not variant.is_active):
        return False
    run = await session.scalar(
        select(SpatialConversionRun)
        .where(
            SpatialConversionRun.media_id == variant.media_id,
            SpatialConversionRun.status.in_(("submitting", "processing")),
            SpatialConversionRun.mss_batch_id.is_not(None),
        )
        .order_by(SpatialConversionRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return False
    run.publish_status = "published" if variant.status == "ready" else "variant_exists"
    ready_variant: MediaVariant | None = variant
    if variant.status == "duplicate":
        ready_variant = await session.get(MediaVariant, resolved_id)
        if ready_variant is None:
            return False
    if ready_variant is None:
        return False
    return await _complete_run_with_variant(
        session,
        run=run,
        variant=ready_variant,
        resolved_id=resolved_id,
    )


async def _complete_run_from_ready_variant(
    session: AsyncSession, *, run: SpatialConversionRun
) -> bool:
    statement = select(MediaVariant).where(
        MediaVariant.media_id == run.media_id,
        MediaVariant.role == "spatial_video",
        MediaVariant.status == "ready",
        MediaVariant.is_active.is_(True),
    )
    if run.gallery_variant_id is not None:
        statement = statement.where(MediaVariant.id == run.gallery_variant_id)
    variant = await session.scalar(statement)
    if variant is None:
        return False
    return await _complete_run_with_variant(
        session, run=run, variant=variant, resolved_id=variant.id
    )


async def _complete_run_with_variant(
    session: AsyncSession,
    *,
    run: SpatialConversionRun,
    variant: MediaVariant,
    resolved_id: UUID,
) -> bool:
    if variant.media_id != run.media_id or not variant.is_active or variant.status != "ready":
        return False
    # A new published result must replace the prior variant. `variant_exists` is
    # explicitly allowed to name that existing active variant.
    if (
        run.previous_variant_id is not None
        and run.previous_variant_id == resolved_id
        and run.publish_status != "variant_exists"
    ):
        return False
    run.gallery_media_id, run.gallery_variant_id = run.media_id, resolved_id
    run.status = "succeeded"
    run.error_code = run.error_message = None
    run.completed_at = datetime.now(UTC)
    await session.commit()
    return True


def _apply_mss_status(run: SpatialConversionRun, payload: Mapping[str, object]) -> None:
    run.response_data, run.queue_position = (
        _bounded_payload(payload),
        _optional_int(payload.get("queue_position")),
    )
    item = _first_file(payload)
    if item:
        run.mss_file_status = _short_string(item.get("status"), 64)
        run.publish_status = _short_string(item.get("publish_status"), 64)
        run.gallery_media_id, run.gallery_variant_id = (
            _optional_uuid(item.get("gallery_media_id")),
            _optional_uuid(item.get("gallery_variant_id")),
        )
        if run.publish_status in {"failed", "skipped"}:
            run.error_code = (
                "MSS_PUBLISH_FAILED" if run.publish_status == "failed" else "MSS_PUBLISH_SKIPPED"
            )
            run.error_message = _short_string(item.get("publish_error"), 512) or (
                "MSS did not publish the generated spatial variant yet."
            )


def _first_file(payload: Mapping[str, object]) -> dict[str, object] | None:
    files = payload.get("files")
    return (
        _bounded_payload(files[0])
        if isinstance(files, list) and files and isinstance(files[0], dict)
        else None
    )


def _optional_uuid(value: object) -> UUID | None:
    try:
        return UUID(value) if isinstance(value, str) else None
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
            result[name] = [
                _bounded_payload(x, depth=depth + 1)
                if isinstance(x, dict)
                else x[:2048]
                if isinstance(x, str)
                else x
                for x in item[:100]
                if isinstance(x, (dict, str, int, float, bool)) or x is None
            ]
        elif isinstance(item, (str, int, float, bool)) or item is None:
            result[name] = item[:2048] if isinstance(item, str) else item
    return result
