from __future__ import annotations

import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import ExportRun, Job, Media
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import safe_managed_path
from comfy_gallery_core.operations.exports import _file_sha256, safe_export_path

MEDIA_ARCHIVE_KIND = "media_archive"
MEDIA_ARCHIVE_SCHEMA_VERSION = "1"
MEDIA_ARCHIVE_MAX_ITEMS = 2_000


def _safe_archive_filename(filename: str, media_id: UUID) -> str:
    """Return a deterministic, path-safe filename for an archive member."""

    normalized = filename.replace("\\", "/")
    basename = PurePosixPath(normalized).name.strip() or "media"
    # Prefixing with the immutable media identity avoids collisions while keeping
    # the original filename recognizable to the user.
    return f"media-{media_id.hex[:12]}-{basename}"


async def create_media_archive(
    session: AsyncSession,
    *,
    export_run: ExportRun,
    job: Job,
    settings: Settings,
) -> ExportRun:
    """Package selected original media bytes into one authenticated ZIP artifact."""

    raw_media_ids = export_run.requested_options.get("media_ids", [])
    if not isinstance(raw_media_ids, list):
        raise IngestionError(
            code="MEDIA_ARCHIVE_SCOPE_INVALID",
            message="The media archive selection is invalid.",
        )
    try:
        media_ids = [UUID(str(value)) for value in raw_media_ids]
    except (TypeError, ValueError) as exc:
        raise IngestionError(
            code="MEDIA_ARCHIVE_SCOPE_INVALID",
            message="The media archive selection contains an invalid media ID.",
        ) from exc
    media_ids = list(dict.fromkeys(media_ids))
    if not media_ids or len(media_ids) > MEDIA_ARCHIVE_MAX_ITEMS:
        raise IngestionError(
            code="MEDIA_ARCHIVE_SCOPE_INVALID",
            message=(
                "A media archive must contain between one and "
                f"{MEDIA_ARCHIVE_MAX_ITEMS:,} media records."
            ),
        )

    export_root = settings.resolved_export_root
    export_root.mkdir(parents=True, exist_ok=True)
    export_run.status = "running"
    export_run.started_at = datetime.now(UTC)
    export_run.error_code = None
    export_run.error_message = None
    job.progress_total = len(media_ids)
    job.progress_current = 0
    job.stage = "write_media_archive"
    await session.commit()

    records = list(
        await session.scalars(
            select(Media).options(selectinload(Media.asset)).where(Media.id.in_(media_ids))
        )
    )
    records_by_id = {record.id: record for record in records}
    missing_record_ids = [str(media_id) for media_id in media_ids if media_id not in records_by_id]
    available_bytes = sum(
        int(record.asset.byte_size) for record in records if record.asset is not None
    )
    free_bytes = shutil.disk_usage(export_root).free
    required_free_bytes = settings.minimum_free_bytes + available_bytes
    if free_bytes < required_free_bytes:
        raise IngestionError(
            code="STORAGE_LOW_SPACE",
            message="There is not enough free space to create the media archive.",
            retryable=True,
            details={
                "required_free_bytes": required_free_bytes,
                "free_bytes": free_bytes,
                "selected_bytes": available_bytes,
            },
        )

    final_name = f"comfy-gallery-media-selection-{export_run.id}.zip"
    final_path = export_root / final_name
    partial_path = export_root / f".{final_name}.partial"
    included: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = [
        {
            "media_id": media_id,
            "reason": "media record not found",
        }
        for media_id in missing_record_ids
    ]

    try:
        with zipfile.ZipFile(
            partial_path,
            mode="x",
            compression=zipfile.ZIP_STORED,
            allowZip64=True,
        ) as archive:
            for index, media_id in enumerate(media_ids, start=1):
                record = records_by_id.get(media_id)
                if record is None or record.asset is None:
                    continue
                try:
                    source_path = safe_managed_path(settings, record.asset.managed_path)
                except IngestionError as error:
                    skipped.append({"media_id": str(media_id), "reason": error.message})
                    continue
                if not source_path.is_file():
                    skipped.append(
                        {
                            "media_id": str(media_id),
                            "filename": record.asset.original_filename,
                            "reason": "managed original is missing",
                        }
                    )
                    continue

                archive_name = _safe_archive_filename(
                    record.asset.original_filename,
                    media_id,
                )
                archive.write(source_path, archive_name)
                included.append(
                    {
                        "media_id": str(media_id),
                        "original_filename": record.asset.original_filename,
                        "archive_path": archive_name,
                        "byte_size": int(source_path.stat().st_size),
                        "sha256": record.asset.sha256,
                    }
                )
                job.progress_current = index
                await session.commit()

            manifest = {
                "media_archive_schema_version": MEDIA_ARCHIVE_SCHEMA_VERSION,
                "archive_id": str(export_run.id),
                "created_at": datetime.now(UTC).isoformat(),
                "requested_count": len(media_ids),
                "included_count": len(included),
                "skipped_count": len(skipped),
                "files": included,
                "skipped": skipped,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )
        partial_path.replace(final_path)

        counts: dict[str, object] = {
            "requested_count": len(media_ids),
            "included_count": len(included),
            "skipped_count": len(skipped),
        }
        export_run.status = "succeeded"
        export_run.artifact_path = final_name
        export_run.byte_size = final_path.stat().st_size
        export_run.sha256 = _file_sha256(final_path, chunk_bytes=settings.hash_chunk_bytes)
        export_run.table_counts = counts
        export_run.completed_at = datetime.now(UTC)
        job.progress_current = len(media_ids)
        await session.commit()
        return export_run
    except IngestionError:
        partial_path.unlink(missing_ok=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        partial_path.unlink(missing_ok=True)
        raise IngestionError(
            code="MEDIA_ARCHIVE_WRITE_FAILED",
            message="The media archive could not be written.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc


def media_archive_path(settings: Settings, export_run: ExportRun) -> Path:
    if export_run.requested_options.get("kind") != MEDIA_ARCHIVE_KIND:
        raise IngestionError(
            code="MEDIA_ARCHIVE_NOT_FOUND",
            message="The media archive was not found.",
        )
    if not export_run.artifact_path:
        raise IngestionError(
            code="MEDIA_ARCHIVE_NOT_READY",
            message="The media archive is not ready to download.",
        )
    return safe_export_path(settings, export_run.artifact_path)
