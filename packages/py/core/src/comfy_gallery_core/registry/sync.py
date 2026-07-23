from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    Job,
    Media,
    RegistrySyncRun,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.jobs import (
    begin_job,
    begin_stage,
    complete_stage,
    fail_job,
    fail_stage,
    load_job,
    succeed_job,
)
from comfy_gallery_core.registry.client import ComfyUIClient
from comfy_gallery_core.registry.models import (
    ModelImportOutcome,
    import_model_inventory,
    resolve_model_references,
)
from comfy_gallery_core.registry.nodes import (
    import_node_definitions,
    resolve_workflow_nodes,
)
from comfy_gallery_core.workflow.extraction import extract_workflow_for_media


async def process_registry_sync_job(
    session: AsyncSession,
    *,
    sync_run_id: UUID,
    job_id: UUID,
    settings: Settings,
) -> None:
    job = await load_job(session, job_id)
    sync_run = await session.get(RegistrySyncRun, sync_run_id)
    if sync_run is None:
        raise IngestionError(
            code="REGISTRY_SYNC_NOT_FOUND",
            message="The requested registry synchronization no longer exists.",
        )
    if not await begin_job(session, job):
        return
    sync_run.status = "running"
    sync_run.started_at = sync_run.started_at or datetime.now(UTC)
    sync_run.completed_at = None
    sync_run.error_code = None
    sync_run.error_message = None
    await session.commit()

    try:
        if sync_run.registry_kind == "node":
            partial = await _sync_nodes(session, sync_run, job, settings)
        elif sync_run.registry_kind == "model":
            partial = await _sync_models(session, sync_run, job, settings)
        elif sync_run.registry_kind == "resolution":
            partial = await _run_resolution(session, sync_run, job, settings)
        else:
            raise IngestionError(
                code="REGISTRY_SYNC_KIND_INVALID",
                message="The registry synchronization kind is not supported.",
            )
        sync_run.status = "partial" if partial else "succeeded"
        sync_run.current_stage = "complete"
        sync_run.completed_at = datetime.now(UTC)
        await session.commit()
        await succeed_job(session, job)
    except IngestionError as error:
        sync_run.status = "failed"
        sync_run.completed_at = datetime.now(UTC)
        sync_run.error_code = error.code
        sync_run.error_message = error.message
        await session.commit()
        await fail_job(session, job, error)
        raise


async def _sync_nodes(
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
    settings: Settings,
) -> bool:
    async with ComfyUIClient(sync_run.source_url, settings) as client:
        system_stats, features, object_info = await _required_stage(
            session,
            sync_run,
            job,
            "node_schema_fetch",
            lambda: _fetch_node_contract(client),
        )
    system = system_stats.get("system")
    system_object = system if isinstance(system, dict) else {}
    sync_run.source_versions = {
        "comfyui_version": _optional_text(system_object.get("comfyui_version")),
        "required_frontend_version": _optional_text(system_object.get("required_frontend_version")),
        "features": features,
    }
    outcome = await _required_stage(
        session,
        sync_run,
        job,
        "node_definition_import",
        lambda: import_node_definitions(
            session,
            source_url=sync_run.source_url,
            comfyui_version=_optional_text(system_object.get("comfyui_version")),
            object_info=object_info,
            maximum_definitions=settings.registry_max_node_definitions,
        ),
    )
    sync_run.node_snapshot_id = outcome.snapshot_id
    _merge_counts(
        sync_run,
        {
            "node_definitions": outcome.definition_count,
            "new_node_definitions": outcome.new_definition_count,
            "automatic_mappings": outcome.automatic_mapping_count,
        },
    )
    resolution = await _required_stage(
        session,
        sync_run,
        job,
        "node_compatibility_resolution",
        lambda: resolve_workflow_nodes(session),
    )
    _merge_counts(
        sync_run,
        {
            "workflow_nodes_matched": resolution.matched_count,
            "historical_node_variants": resolution.historical_count,
            "ambiguous_node_matches": resolution.ambiguous_count,
            "unresolved_node_matches": resolution.unresolved_count,
        },
    )
    reprocessed = await _required_stage(
        session,
        sync_run,
        job,
        "workflow_semantic_reprocess",
        lambda: _reprocess_workflows(session, settings),
    )
    _merge_counts(sync_run, {"workflows_reprocessed": reprocessed})
    await session.commit()
    return False


async def _sync_models(
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
    settings: Settings,
) -> bool:
    run_scans = bool(sync_run.requested_options.get("run_scans", True))
    fetch_civitai = bool(sync_run.requested_options.get("fetch_civitai", True))
    partial = False
    async with ComfyUIClient(sync_run.source_url, settings) as client:
        if run_scans:
            scan_result = await _optional_stage(
                session,
                sync_run,
                job,
                "lora_manager_local_scan",
                lambda: _scan_inventories(client),
            )
            partial = partial or scan_result is None
        if fetch_civitai:
            fetch_result = await _optional_stage(
                session,
                sync_run,
                job,
                "lora_manager_civitai_fetch",
                lambda: _fetch_civitai(client),
            )
            partial = partial or fetch_result is None

        inventory = await _required_stage(
            session,
            sync_run,
            job,
            "model_inventory_fetch",
            lambda: _fetch_model_inventory(client),
        )
        lora_items, checkpoint_items, folder_models = inventory
        metadata_result = await _optional_stage(
            session,
            sync_run,
            job,
            "model_metadata_fetch",
            lambda: _fetch_inventory_metadata(
                client,
                lora_items=lora_items,
                checkpoint_items=checkpoint_items,
                concurrency=settings.registry_metadata_concurrency,
            ),
        )
        partial = partial or metadata_result is None
        metadata_by_path = metadata_result or {}

    imported = await _required_stage(
        session,
        sync_run,
        job,
        "model_registry_import",
        lambda: import_model_inventory(
            session,
            lora_items=lora_items,
            checkpoint_items=checkpoint_items,
            folder_models=folder_models,
            metadata_by_path=metadata_by_path,
            enrichment_attempted=fetch_civitai,
        ),
    )
    _record_model_import(sync_run, imported, lora_items, checkpoint_items)
    resolved = await _required_stage(
        session,
        sync_run,
        job,
        "workflow_model_resolution",
        lambda: resolve_model_references(session),
    )
    _merge_counts(
        sync_run,
        {
            "model_references": resolved.reference_count,
            "resolved_model_references": resolved.resolved_count,
            "ambiguous_model_references": resolved.ambiguous_count,
            "historical_model_references": resolved.historical_count,
            "model_usages": resolved.usage_count,
            "lora_series": resolved.series_count,
        },
    )
    await session.commit()
    return partial


async def _run_resolution(
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
    settings: Settings,
) -> bool:
    if bool(sync_run.requested_options.get("reprocess_workflows", False)):
        reprocessed = await _required_stage(
            session,
            sync_run,
            job,
            "workflow_semantic_reprocess",
            lambda: _reprocess_workflows(session, settings),
        )
        _merge_counts(sync_run, {"workflows_reprocessed": reprocessed})
    resolved = await _required_stage(
        session,
        sync_run,
        job,
        "workflow_model_resolution",
        lambda: resolve_model_references(session),
    )
    _merge_counts(
        sync_run,
        {
            "model_references": resolved.reference_count,
            "resolved_model_references": resolved.resolved_count,
            "ambiguous_model_references": resolved.ambiguous_count,
            "historical_model_references": resolved.historical_count,
            "model_usages": resolved.usage_count,
            "lora_series": resolved.series_count,
        },
    )
    await session.commit()
    return False


async def _required_stage[T](
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
    stage: str,
    operation: Callable[[], Awaitable[T]],
) -> T:
    sync_run.current_stage = stage
    _set_stage(sync_run, stage, status="running")
    await session.commit()
    attempt = await begin_stage(session, job, stage)
    try:
        result = await operation()
    except IngestionError as error:
        await fail_stage(session, attempt, error)
        _set_stage(
            sync_run,
            stage,
            status="failed",
            code=error.code,
            message=error.message,
        )
        await session.commit()
        raise
    except Exception as exception:
        failure = IngestionError(
            code="REGISTRY_STAGE_INTERNAL_ERROR",
            message=f"The {stage.replace('_', ' ')} stage failed unexpectedly.",
            details={"exception_type": type(exception).__name__},
        )
        await fail_stage(session, attempt, failure)
        _set_stage(
            sync_run,
            stage,
            status="failed",
            code=failure.code,
            message=failure.message,
        )
        await session.commit()
        raise failure from exception
    await complete_stage(session, attempt)
    _set_stage(sync_run, stage, status="succeeded")
    job.progress_current += 1
    await session.commit()
    return result


async def _optional_stage[T](
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
    stage: str,
    operation: Callable[[], Awaitable[T]],
) -> T | None:
    try:
        return await _required_stage(
            session,
            sync_run,
            job,
            stage,
            operation,
        )
    except IngestionError as error:
        _set_stage(
            sync_run,
            stage,
            status="failed_optional",
            code=error.code,
            message=error.message,
        )
        await session.commit()
        return None


async def _fetch_node_contract(
    client: ComfyUIClient,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    system_stats, features, object_info = await asyncio.gather(
        client.system_stats(),
        client.features(),
        client.object_info(),
    )
    return system_stats, features, object_info


async def _scan_inventories(
    client: ComfyUIClient,
) -> dict[str, dict[str, object]]:
    loras, checkpoints = await asyncio.gather(
        client.lora_manager_scan("loras"),
        client.lora_manager_scan("checkpoints"),
    )
    return {"loras": loras, "checkpoints": checkpoints}


async def _fetch_civitai(
    client: ComfyUIClient,
) -> dict[str, dict[str, object]]:
    loras, checkpoints = await asyncio.gather(
        client.lora_manager_fetch_all("loras"),
        client.lora_manager_fetch_all("checkpoints"),
    )
    return {"loras": loras, "checkpoints": checkpoints}


async def _fetch_model_inventory(
    client: ComfyUIClient,
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, list[str]]]:
    loras, checkpoints, folder_models = await asyncio.gather(
        client.lora_manager_list("loras"),
        client.lora_manager_list("checkpoints"),
        client.current_model_lists(),
    )
    return loras, checkpoints, folder_models


async def _fetch_inventory_metadata(
    client: ComfyUIClient,
    *,
    lora_items: list[dict[str, object]],
    checkpoint_items: list[dict[str, object]],
    concurrency: int,
) -> dict[str, dict[str, object]]:
    semaphore = asyncio.Semaphore(concurrency)
    requests: list[tuple[str, str]] = []
    for kind, items in (("loras", lora_items), ("checkpoints", checkpoint_items)):
        for item in items:
            path = _optional_text(item.get("file_path"))
            if path is not None:
                requests.append((kind, path))

    async def fetch(kind: str, path: str) -> tuple[str, dict[str, object]]:
        async with semaphore:
            return path, await client.lora_manager_metadata(kind, path)

    results = await asyncio.gather(
        *(fetch(kind, path) for kind, path in requests),
        return_exceptions=True,
    )
    metadata: dict[str, dict[str, object]] = {}
    failure_count = 0
    for result in results:
        if isinstance(result, BaseException):
            failure_count += 1
        else:
            path, payload = result
            metadata[path] = payload
    if failure_count:
        raise IngestionError(
            code="LORA_MANAGER_METADATA_PARTIAL",
            message="Some LoRA Manager metadata records could not be read.",
            retryable=True,
            details={
                "requested_count": len(requests),
                "failed_count": failure_count,
            },
        )
    return metadata


async def _reprocess_workflows(
    session: AsyncSession,
    settings: Settings,
) -> int:
    media_ids = list(
        await session.scalars(
            select(Media.id)
            .join(WorkflowSnapshot, WorkflowSnapshot.media_id == Media.id)
            .order_by(Media.created_at)
        )
    )
    for media_id in media_ids:
        await extract_workflow_for_media(
            session,
            media_id=media_id,
            settings=settings,
            reason="registry_reprocess",
        )
    return len(media_ids)


def _record_model_import(
    sync_run: RegistrySyncRun,
    outcome: ModelImportOutcome,
    lora_items: list[dict[str, object]],
    checkpoint_items: list[dict[str, object]],
) -> None:
    _merge_counts(
        sync_run,
        {
            "lora_manager_loras": len(lora_items),
            "lora_manager_checkpoints": len(checkpoint_items),
            "present_model_artifacts": outcome.artifact_count,
            "hash_verified_artifacts": outcome.hash_verified_count,
            "comfyui_fallback_artifacts": outcome.fallback_count,
            "enriched_artifacts": outcome.enriched_count,
        },
    )


def _set_stage(
    sync_run: RegistrySyncRun,
    stage: str,
    *,
    status: str,
    code: str | None = None,
    message: str | None = None,
) -> None:
    stages = dict(sync_run.stage_status)
    stages[stage] = {
        "status": status,
        "code": code,
        "message": message,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    sync_run.stage_status = stages


def _merge_counts(sync_run: RegistrySyncRun, values: dict[str, object]) -> None:
    sync_run.counts = {**sync_run.counts, **values}


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None
