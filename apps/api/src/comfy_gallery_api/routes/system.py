from __future__ import annotations

import asyncio
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import func, select

from comfy_gallery_api import __version__
from comfy_gallery_api.dependencies import CsrfPrincipalDep, DbSessionDep, PrincipalDep, SettingsDep
from comfy_gallery_api.media_schemas import SpatialAvailabilityReconcileResponse
from comfy_gallery_api.operations_schemas import OperationalStatusResponse, StatusCheck
from comfy_gallery_api.services import check_database, check_redis
from comfy_gallery_core.db.models import ExportRun, Job, RegistrySyncRun, ScanBatch
from comfy_gallery_core.media.variants import reconcile_spatial_availability
from comfy_gallery_core.operations.heartbeat import (
    WORKER_HEARTBEAT_FILENAME,
    load_worker_heartbeat,
)

router = APIRouter(prefix="/api/v1/system", tags=["system"])


def _disk_check(
    path: Path,
    *,
    minimum_free_bytes: int,
    warning_percent: float,
) -> StatusCheck:
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return StatusCheck(status="error", detail="storage path is unavailable")
    used_percent = ((usage.total - usage.free) / usage.total * 100) if usage.total else 100.0
    data: dict[str, object] = {
        "total_bytes": usage.total,
        "free_bytes": usage.free,
        "used_percent": round(used_percent, 1),
    }
    if usage.free < minimum_free_bytes:
        return StatusCheck(
            status="error",
            detail="free space is below the configured safety reserve",
            data=data,
        )
    if used_percent >= warning_percent:
        return StatusCheck(
            status="warning",
            detail="filesystem usage is above the warning threshold",
            data=data,
        )
    return StatusCheck(status="ok", data=data)


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _worker_check(settings: SettingsDep) -> StatusCheck:
    heartbeat = load_worker_heartbeat(settings.resolved_runtime_root / WORKER_HEARTBEAT_FILENAME)
    if heartbeat is None:
        return StatusCheck(status="warning", detail="no worker heartbeat has been recorded")
    updated_at = _parse_datetime(heartbeat.get("updated_at"))
    if updated_at is None:
        return StatusCheck(status="warning", detail="worker heartbeat is malformed")
    age_seconds = max(0.0, (datetime.now(UTC) - updated_at).total_seconds())
    data: dict[str, object] = {
        "state": str(heartbeat.get("state", "unknown")),
        "version": str(heartbeat.get("version", "unknown")),
        "updated_at": updated_at.isoformat(),
        "age_seconds": round(age_seconds, 1),
    }
    if heartbeat.get("state") != "running" or age_seconds > settings.worker_stale_after_seconds:
        return StatusCheck(status="error", detail="worker heartbeat is stale", data=data)
    return StatusCheck(status="ok", data=data)


def _backup_check(settings: SettingsDep) -> StatusCheck:
    status_path = settings.resolved_backup_root / ".backup-status.json"
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return StatusCheck(status="warning", detail="no successful database backup is recorded")
    except (OSError, json.JSONDecodeError):
        return StatusCheck(status="warning", detail="database backup status is unreadable")
    if not isinstance(payload, dict):
        return StatusCheck(status="warning", detail="database backup status is malformed")
    if payload.get("status") != "ok":
        return StatusCheck(
            status="error",
            detail="the latest scheduled database backup failed",
            data={"attempted_at": payload.get("attempted_at", "unknown")},
        )
    completed_at = _parse_datetime(payload.get("completed_at"))
    if completed_at is None:
        return StatusCheck(status="warning", detail="database backup timestamp is malformed")
    age_hours = max(0.0, (datetime.now(UTC) - completed_at).total_seconds() / 3600)
    data: dict[str, object] = {
        "completed_at": completed_at.isoformat(),
        "age_hours": round(age_hours, 1),
        "backup_id": str(payload.get("backup_id", "")),
        "byte_size": payload.get("byte_size", 0),
    }
    if age_hours > settings.backup_expected_interval_hours:
        return StatusCheck(status="warning", detail="database backup is overdue", data=data)
    return StatusCheck(status="ok", data=data)


async def _job_check(session: DbSessionDep, settings: SettingsDep) -> StatusCheck:
    counts = {
        status: count
        for status, count in (
            await session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status))
        ).all()
    }
    cutoff = datetime.now(UTC) - timedelta(seconds=settings.job_stale_after_seconds)
    stale_count = (
        await session.scalar(
            select(func.count(Job.id)).where(
                Job.status == "running",
                Job.started_at < cutoff,
            )
        )
        or 0
    )
    data: dict[str, object] = {
        "counts": counts,
        "active_count": counts.get("queued", 0) + counts.get("running", 0),
        "failed_count": counts.get("failed", 0),
        "stale_running_count": stale_count,
    }
    if stale_count:
        return StatusCheck(status="warning", detail="one or more jobs may be stuck", data=data)
    return StatusCheck(status="ok", data=data)


async def _activity_check(session: DbSessionDep) -> StatusCheck:
    latest_scan = await session.scalar(
        select(ScanBatch).order_by(ScanBatch.created_at.desc()).limit(1)
    )
    latest_sync = await session.scalar(
        select(RegistrySyncRun).order_by(RegistrySyncRun.created_at.desc()).limit(1)
    )
    latest_export = await session.scalar(
        select(ExportRun).order_by(ExportRun.created_at.desc()).limit(1)
    )
    data: dict[str, object] = {
        "last_scan": (
            {
                "status": latest_scan.status,
                "created_at": latest_scan.created_at.isoformat(),
                "completed_at": (
                    latest_scan.completed_at.isoformat() if latest_scan.completed_at else None
                ),
            }
            if latest_scan
            else None
        ),
        "last_registry_sync": (
            {
                "status": latest_sync.status,
                "created_at": latest_sync.created_at.isoformat(),
                "completed_at": (
                    latest_sync.completed_at.isoformat() if latest_sync.completed_at else None
                ),
            }
            if latest_sync
            else None
        ),
        "last_export": (
            {
                "status": latest_export.status,
                "created_at": latest_export.created_at.isoformat(),
                "completed_at": (
                    latest_export.completed_at.isoformat() if latest_export.completed_at else None
                ),
            }
            if latest_export
            else None
        ),
    }
    if latest_sync and latest_sync.status == "failed":
        return StatusCheck(
            status="warning",
            detail="latest optional registry synchronization failed; cached data remains available",
            data=data,
        )
    return StatusCheck(status="ok", data=data)


@router.get("/status", response_model=OperationalStatusResponse)
async def system_status(
    _principal: PrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> OperationalStatusResponse:
    database_check, redis_check = await asyncio.gather(
        check_database(session),
        check_redis(settings.redis_url),
    )
    checks: dict[str, StatusCheck] = {
        "database": StatusCheck(
            status=database_check.status,
            detail=database_check.detail,
        ),
        "redis": StatusCheck(status=redis_check.status, detail=redis_check.detail),
        "worker": _worker_check(settings),
        "managed_storage": _disk_check(
            settings.resolved_managed_root,
            minimum_free_bytes=settings.minimum_free_bytes,
            warning_percent=settings.disk_warning_percent,
        ),
        "staging_storage": _disk_check(
            settings.resolved_staging_root,
            minimum_free_bytes=settings.minimum_free_bytes,
            warning_percent=settings.disk_warning_percent,
        ),
        "export_storage": _disk_check(
            settings.resolved_export_root,
            minimum_free_bytes=settings.minimum_free_bytes,
            warning_percent=settings.disk_warning_percent,
        ),
        "database_backup": _backup_check(settings),
    }
    if database_check.status == "ok":
        checks["jobs"] = await _job_check(session, settings)
        checks["recent_activity"] = await _activity_check(session)
    else:
        checks["jobs"] = StatusCheck(status="error", detail="job state is unavailable")
        checks["recent_activity"] = StatusCheck(
            status="error",
            detail="activity state is unavailable",
        )
    warnings = [
        f"{name}: {check.detail or check.status}"
        for name, check in checks.items()
        if check.status != "ok"
    ]
    return OperationalStatusResponse(
        status="ok" if not warnings else "degraded",
        service="comfy-gallery",
        version=__version__,
        checks=checks,
        warnings=warnings,
    )


@router.post(
    "/reconcile-spatial-availability",
    response_model=SpatialAvailabilityReconcileResponse,
)
async def reconcile_spatial_availability_projection(
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> SpatialAvailabilityReconcileResponse:
    updated = await reconcile_spatial_availability(session)
    return SpatialAvailabilityReconcileResponse(updated_media_count=updated)
