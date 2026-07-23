from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import zipfile
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core import __version__
from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import ExportRun
from comfy_gallery_core.media.errors import IngestionError

EXPORT_SCHEMA_VERSION = "1"

# The portable bundle intentionally excludes password hashes, sessions, API tokens,
# transient upload state, worker jobs, and export bookkeeping.
EXPORT_TABLE_NAMES = (
    "media",
    "media_asset",
    "derivative",
    "source_root",
    "scan_batch",
    "source_occurrence",
    "workflow_snapshot",
    "workflow_node",
    "workflow_edge",
    "workflow_value",
    "extraction_run",
    "semantic_observation",
    "node_schema_snapshot",
    "node_definition",
    "node_semantic_mapping",
    "registry_sync_run",
    "model_artifact",
    "model_reference",
    "model_usage",
    "lora_series",
    "lora_series_member",
    "comparison_group",
    "comparison_group_member",
    "criterion",
    "criterion_version",
    "evaluation_template",
    "evaluation_template_item",
    "evaluation",
    "evaluation_score",
    "score_revision",
    "evaluation_disposition_revision",
    "media_collection",
    "collection_item",
    "tag",
    "media_tag",
    "saved_filter",
    "review_session",
    "review_session_item",
    "weighting_profile",
    "analysis_run",
    "analysis_member",
    "analysis_score_snapshot",
    "analysis_result",
)
WORKFLOW_EVIDENCE_TABLES = {
    "workflow_snapshot",
    "workflow_node",
    "workflow_edge",
    "workflow_value",
    "extraction_run",
    "semantic_observation",
}


def _json_value(value: object) -> object:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    return value


def _json_line(row: Mapping[Any, object]) -> bytes:
    payload = {str(key): _json_value(value) for key, value in row.items()}
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    ).encode()


def _file_sha256(path: Path, *, chunk_bytes: int) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_bytes), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _write_table_jsonl(
    session: AsyncSession,
    *,
    table: Table,
    destination: Path,
) -> int:
    primary_keys = list(table.primary_key.columns)
    query = select(table)
    if primary_keys:
        query = query.order_by(*primary_keys)
    result = await session.stream(query.execution_options(yield_per=100))
    count = 0
    with destination.open("wb") as handle:
        async for row in result.mappings():
            handle.write(_json_line(row))
            count += 1
    return count


async def _write_principals(session: AsyncSession, destination: Path) -> int:
    table = Base.metadata.tables["app_user"]
    query = select(
        table.c.id,
        table.c.username,
        table.c.is_active,
        table.c.created_at,
        table.c.updated_at,
    ).order_by(table.c.id)
    rows = (await session.execute(query)).mappings()
    count = 0
    with destination.open("wb") as handle:
        for row in rows:
            handle.write(_json_line(row))
            count += 1
    return count


def _write_csv(path: Path, rows: Iterable[Mapping[Any, object]], columns: list[str]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _json_value(value) for key, value in row.items()})
            count += 1
    return count


async def _write_evaluation_csv(session: AsyncSession, destination: Path) -> int:
    tables = Base.metadata.tables
    evaluation = tables["evaluation"]
    score = tables["evaluation_score"]
    criterion_version = tables["criterion_version"]
    criterion = tables["criterion"]
    media_asset = tables["media_asset"]
    query = (
        select(
            evaluation.c.id.label("evaluation_id"),
            evaluation.c.media_id,
            media_asset.c.sha256.label("media_sha256"),
            evaluation.c.evaluation_kind,
            evaluation.c.progress_state,
            evaluation.c.is_trash,
            evaluation.c.version.label("evaluation_version"),
            criterion.c.stable_key.label("criterion_key"),
            criterion_version.c.version.label("criterion_version"),
            score.c.state,
            score.c.value,
            score.c.na_reason,
            score.c.updated_at,
        )
        .join(score, score.c.evaluation_id == evaluation.c.id)
        .join(
            criterion_version,
            criterion_version.c.id == score.c.criterion_version_id,
        )
        .join(criterion, criterion.c.id == criterion_version.c.criterion_id)
        .join(media_asset, media_asset.c.media_id == evaluation.c.media_id)
        .order_by(evaluation.c.media_id, criterion.c.stable_key)
    )
    rows = (await session.execute(query)).mappings()
    columns = [
        "evaluation_id",
        "media_id",
        "media_sha256",
        "evaluation_kind",
        "progress_state",
        "is_trash",
        "evaluation_version",
        "criterion_key",
        "criterion_version",
        "state",
        "value",
        "na_reason",
        "updated_at",
    ]
    return _write_csv(destination, rows, columns)


async def _write_analysis_csv(session: AsyncSession, destination: Path) -> int:
    table = Base.metadata.tables["analysis_result"]
    columns = [column.name for column in table.columns]
    rows = (
        await session.execute(select(table).order_by(table.c.run_id, table.c.group_key))
    ).mappings()
    return _write_csv(destination, rows, columns)


async def create_portable_export(
    session: AsyncSession,
    *,
    export_run: ExportRun,
    settings: Settings,
) -> ExportRun:
    export_root = settings.resolved_export_root
    export_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(export_root).free
    if free_bytes < settings.minimum_free_bytes:
        raise IngestionError(
            code="STORAGE_LOW_SPACE",
            message="There is not enough free space to create a portable export.",
            retryable=True,
            details={
                "required_free_bytes": settings.minimum_free_bytes,
                "free_bytes": free_bytes,
            },
        )

    export_run.status = "running"
    export_run.started_at = datetime.now(UTC)
    export_run.error_code = None
    export_run.error_message = None
    await session.commit()

    final_name = f"comfy-gallery-export-{export_run.id}.zip"
    final_path = export_root / final_name
    partial_path = export_root / f".{final_name}.partial"
    counts: dict[str, int] = {}
    try:
        with tempfile.TemporaryDirectory(prefix=".export-", dir=export_root) as temporary:
            staging = Path(temporary)
            jsonl_root = staging / "jsonl"
            csv_root = staging / "csv"
            jsonl_root.mkdir()
            csv_root.mkdir()

            counts["principals"] = await _write_principals(
                session,
                jsonl_root / "principals.jsonl",
            )
            include_workflow_evidence = bool(
                export_run.requested_options.get("include_workflow_evidence", True)
            )
            table_names = [
                name
                for name in EXPORT_TABLE_NAMES
                if include_workflow_evidence or name not in WORKFLOW_EVIDENCE_TABLES
            ]
            for table_name in table_names:
                table = Base.metadata.tables[table_name]
                counts[table_name] = await _write_table_jsonl(
                    session,
                    table=table,
                    destination=jsonl_root / f"{table_name}.jsonl",
                )

            counts["evaluation_scores_csv"] = await _write_evaluation_csv(
                session,
                csv_root / "evaluation_scores.csv",
            )
            counts["analysis_results_csv"] = await _write_analysis_csv(
                session,
                csv_root / "analysis_results.csv",
            )

            files = []
            for path in sorted(staging.rglob("*")):  # noqa: ASYNC240
                if not path.is_file():
                    continue
                files.append(
                    {
                        "path": path.relative_to(staging).as_posix(),
                        "byte_size": path.stat().st_size,
                        "sha256": _file_sha256(path, chunk_bytes=settings.hash_chunk_bytes),
                    }
                )
            manifest = {
                "export_schema_version": EXPORT_SCHEMA_VERSION,
                "application_version": __version__,
                "export_id": str(export_run.id),
                "created_at": datetime.now(UTC).isoformat(),
                "contents": {
                    "format": "table-shaped JSON Lines with inspection CSV summaries",
                    "counts": counts,
                    "files": files,
                },
                "security": {
                    "excluded": [
                        "password hashes",
                        "web sessions",
                        "API token hashes and values",
                        "transient worker jobs",
                    ],
                    "warning": (
                        "The bundle can contain private prompts, paths, and workflow metadata."
                    ),
                },
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with zipfile.ZipFile(
                partial_path,
                mode="x",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
                allowZip64=True,
            ) as archive:
                for path in sorted(staging.rglob("*")):  # noqa: ASYNC240
                    if path.is_file():
                        archive.write(path, path.relative_to(staging).as_posix())
            partial_path.replace(final_path)

        export_run.status = "succeeded"
        export_run.artifact_path = final_name
        export_run.byte_size = final_path.stat().st_size
        export_run.sha256 = _file_sha256(final_path, chunk_bytes=settings.hash_chunk_bytes)
        export_run.table_counts = {key: value for key, value in counts.items()}
        export_run.completed_at = datetime.now(UTC)
        await session.commit()
        return export_run
    except IngestionError:
        partial_path.unlink(missing_ok=True)
        raise
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        partial_path.unlink(missing_ok=True)
        raise IngestionError(
            code="EXPORT_WRITE_FAILED",
            message="The portable export could not be written.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc


def safe_export_path(settings: Settings, relative_path: str) -> Path:
    root = settings.resolved_export_root
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise IngestionError(
            code="EXPORT_PATH_INVALID",
            message="The export artifact path is outside the configured export root.",
        )
    return candidate
