from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from comfy_gallery_api.dependencies import (
    CsrfPrincipalDep,
    DbSessionDep,
    PrincipalDep,
    SettingsDep,
)
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.media_schemas import JobResponse
from comfy_gallery_api.registry_schemas import (
    ComparisonGroupMemberResponse,
    ComparisonGroupRequest,
    ComparisonGroupResponse,
    LoraSeriesMemberResponse,
    LoraSeriesMemberUpdateRequest,
    LoraSeriesMergeRequest,
    LoraSeriesResponse,
    LoraSeriesSplitRequest,
    LoraSeriesUpdateRequest,
    ModelArtifactDetailResponse,
    ModelArtifactPageResponse,
    ModelArtifactResponse,
    ModelArtifactUpdatedResponse,
    ModelArtifactUpdateRequest,
    ModelReferenceLinkedResponse,
    ModelReferenceLinkRequest,
    ModelReferencePageResponse,
    ModelReferenceResponse,
    ModelRegistrySyncRequest,
    NodeDefinitionDetailResponse,
    NodeDefinitionListItemResponse,
    NodeDefinitionPageResponse,
    NodeMappingCreatedResponse,
    NodeMappingCreateRequest,
    NodeMappingResponse,
    RegistrySyncCreatedResponse,
    RegistrySyncRequest,
    RegistrySyncRunResponse,
)
from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import (
    ComparisonGroup,
    ComparisonGroupMember,
    Job,
    LoraSeries,
    LoraSeriesMember,
    ModelArtifact,
    ModelReference,
    NodeDefinition,
    RegistrySyncRun,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.queue import enqueue_registry_sync
from comfy_gallery_core.registry.client import normalize_comfyui_url
from comfy_gallery_core.registry.models import (
    link_model_reference,
    merge_lora_series,
    split_lora_series,
    update_artifact_fields,
    update_series_member,
)
from comfy_gallery_core.registry.nodes import set_manual_mapping

router = APIRouter(prefix="/api/v1", tags=["registries"])


@router.post(
    "/node-registry/sync",
    response_model=RegistrySyncCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_node_registry(
    request: RegistrySyncRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> RegistrySyncCreatedResponse:
    source_url = _source_url(request.base_url, settings)
    return await _create_sync(
        session,
        registry_kind="node",
        source_url=source_url,
        options={},
        progress_total=4,
    )


@router.post(
    "/model-registry/sync",
    response_model=RegistrySyncCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_model_registry(
    request: ModelRegistrySyncRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> RegistrySyncCreatedResponse:
    source_url = _source_url(request.base_url, settings)
    return await _create_sync(
        session,
        registry_kind="model",
        source_url=source_url,
        options={
            "run_scans": request.run_scans,
            "fetch_civitai": request.fetch_civitai,
        },
        progress_total=6,
    )


@router.get(
    "/registry-sync-runs",
    response_model=list[RegistrySyncRunResponse],
)
async def list_registry_sync_runs(
    _principal: PrincipalDep,
    session: DbSessionDep,
    registry_kind: str | None = None,
    limit: int = Query(default=25, ge=1, le=200),
) -> list[RegistrySyncRunResponse]:
    query = select(RegistrySyncRun)
    if registry_kind:
        query = query.where(RegistrySyncRun.registry_kind == registry_kind)
    runs = list(
        await session.scalars(query.order_by(RegistrySyncRun.created_at.desc()).limit(limit))
    )
    return [RegistrySyncRunResponse.model_validate(run) for run in runs]


@router.get(
    "/registry-sync-runs/{sync_run_id}",
    response_model=RegistrySyncRunResponse,
)
async def get_registry_sync_run(
    sync_run_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> RegistrySyncRunResponse:
    return RegistrySyncRunResponse.model_validate(
        await _get_or_404(
            session,
            RegistrySyncRun,
            sync_run_id,
            code="REGISTRY_SYNC_NOT_FOUND",
            message="The registry synchronization was not found.",
        )
    )


@router.get(
    "/node-definitions",
    response_model=NodeDefinitionPageResponse,
)
async def list_node_definitions(
    _principal: PrincipalDep,
    session: DbSessionDep,
    search: str | None = None,
    mapping_state: str | None = None,
    presence: str | None = Query(default=None, pattern="^(present|historical)$"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> NodeDefinitionPageResponse:
    filters: list[ColumnElement[bool]] = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                NodeDefinition.class_type.ilike(pattern),
                NodeDefinition.display_name.ilike(pattern),
                NodeDefinition.python_module.ilike(pattern),
            )
        )
    if mapping_state:
        filters.append(NodeDefinition.mapping_state == mapping_state)
    if presence == "present":
        filters.append(NodeDefinition.is_present.is_(True))
    elif presence == "historical":
        filters.append(NodeDefinition.is_present.is_(False))
    total = int(
        await session.scalar(select(func.count()).select_from(NodeDefinition).where(*filters)) or 0
    )
    definitions = list(
        await session.scalars(
            select(NodeDefinition)
            .where(*filters)
            .order_by(
                NodeDefinition.workflow_occurrence_count.desc(),
                NodeDefinition.class_type,
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return NodeDefinitionPageResponse(
        items=[
            NodeDefinitionListItemResponse.model_validate(definition) for definition in definitions
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/node-definitions/{definition_id}",
    response_model=NodeDefinitionDetailResponse,
)
async def get_node_definition(
    definition_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> NodeDefinitionDetailResponse:
    definition = await session.scalar(
        select(NodeDefinition)
        .options(selectinload(NodeDefinition.mappings))
        .where(NodeDefinition.id == definition_id)
    )
    if definition is None:
        raise ApiError(
            status_code=404,
            code="NODE_DEFINITION_NOT_FOUND",
            message="The node definition was not found.",
        )
    return NodeDefinitionDetailResponse.model_validate(definition)


@router.post(
    "/node-mappings",
    response_model=NodeMappingCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_node_mapping(
    request: NodeMappingCreateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> NodeMappingCreatedResponse:
    definition = await _get_or_404(
        session,
        NodeDefinition,
        request.node_definition_id,
        code="NODE_DEFINITION_NOT_FOUND",
        message="The node definition was not found.",
    )
    try:
        mapping = await set_manual_mapping(
            session,
            definition=definition,
            locator=request.locator,
            semantic_type=request.semantic_type,
            role=request.role,
        )
    except IngestionError as error:
        raise _registry_api_error(error) from error
    job = await _create_resolution_job(session, reprocess_workflows=True)
    return NodeMappingCreatedResponse(
        mapping=NodeMappingResponse.model_validate(mapping),
        job=JobResponse.model_validate(job),
    )


@router.get("/models", response_model=ModelArtifactPageResponse)
async def list_models(
    _principal: PrincipalDep,
    session: DbSessionDep,
    search: str | None = None,
    artifact_type: str | None = None,
    availability: str | None = None,
    enrichment_state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ModelArtifactPageResponse:
    filters: list[ColumnElement[bool]] = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                ModelArtifact.display_name.ilike(pattern),
                ModelArtifact.file_name.ilike(pattern),
                ModelArtifact.file_path.ilike(pattern),
                ModelArtifact.architecture_family.ilike(pattern),
                ModelArtifact.lineage.ilike(pattern),
            )
        )
    if artifact_type:
        filters.append(ModelArtifact.artifact_type == artifact_type)
    if availability:
        filters.append(ModelArtifact.availability == availability)
    if enrichment_state:
        filters.append(ModelArtifact.enrichment_state == enrichment_state)
    total = int(
        await session.scalar(select(func.count()).select_from(ModelArtifact).where(*filters)) or 0
    )
    artifacts = list(
        await session.scalars(
            select(ModelArtifact)
            .where(*filters)
            .order_by(ModelArtifact.display_name)
            .offset(offset)
            .limit(limit)
        )
    )
    return ModelArtifactPageResponse(
        items=[ModelArtifactResponse.model_validate(artifact) for artifact in artifacts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/models/{artifact_id}", response_model=ModelArtifactDetailResponse)
async def get_model(
    artifact_id: UUID,
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> ModelArtifactDetailResponse:
    artifact = await _get_or_404(
        session,
        ModelArtifact,
        artifact_id,
        code="MODEL_ARTIFACT_NOT_FOUND",
        message="The model artifact was not found.",
    )
    return ModelArtifactDetailResponse.model_validate(artifact)


@router.patch(
    "/models/{artifact_id}",
    response_model=ModelArtifactUpdatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def update_model(
    artifact_id: UUID,
    request: ModelArtifactUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ModelArtifactUpdatedResponse:
    artifact = await _get_or_404(
        session,
        ModelArtifact,
        artifact_id,
        code="MODEL_ARTIFACT_NOT_FOUND",
        message="The model artifact was not found.",
    )
    try:
        artifact = await update_artifact_fields(
            session,
            artifact=artifact,
            values=request.model_dump(exclude_unset=True),
        )
    except IngestionError as error:
        raise _registry_api_error(error) from error
    job = await _create_resolution_job(session, reprocess_workflows=False)
    return ModelArtifactUpdatedResponse(
        artifact=ModelArtifactResponse.model_validate(artifact),
        job=JobResponse.model_validate(job),
    )


@router.get(
    "/model-references",
    response_model=ModelReferencePageResponse,
)
async def list_model_references(
    _principal: PrincipalDep,
    session: DbSessionDep,
    search: str | None = None,
    reference_type: str | None = None,
    resolution_state: str | None = None,
    availability: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ModelReferencePageResponse:
    filters: list[ColumnElement[bool]] = []
    if search:
        filters.append(ModelReference.raw_value.ilike(f"%{search.strip()}%"))
    if reference_type:
        filters.append(ModelReference.reference_type == reference_type)
    if resolution_state:
        filters.append(ModelReference.resolution_state == resolution_state)
    if availability:
        filters.append(ModelReference.availability == availability)
    total = int(
        await session.scalar(select(func.count()).select_from(ModelReference).where(*filters)) or 0
    )
    references = list(
        await session.scalars(
            select(ModelReference)
            .where(*filters)
            .order_by(
                ModelReference.occurrence_count.desc(),
                ModelReference.raw_value,
            )
            .offset(offset)
            .limit(limit)
        )
    )
    return ModelReferencePageResponse(
        items=[ModelReferenceResponse.model_validate(reference) for reference in references],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/model-references/{reference_id}/link",
    response_model=ModelReferenceLinkedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def link_reference(
    reference_id: UUID,
    request: ModelReferenceLinkRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ModelReferenceLinkedResponse:
    reference = await _get_or_404(
        session,
        ModelReference,
        reference_id,
        code="MODEL_REFERENCE_NOT_FOUND",
        message="The model reference was not found.",
    )
    artifact = (
        await _get_or_404(
            session,
            ModelArtifact,
            request.artifact_id,
            code="MODEL_ARTIFACT_NOT_FOUND",
            message="The model artifact was not found.",
        )
        if request.artifact_id is not None
        else None
    )
    reference = await link_model_reference(
        session,
        reference=reference,
        artifact=artifact,
    )
    job = await _create_resolution_job(session, reprocess_workflows=False)
    return ModelReferenceLinkedResponse(
        reference=ModelReferenceResponse.model_validate(reference),
        job=JobResponse.model_validate(job),
    )


@router.get("/lora-series", response_model=list[LoraSeriesResponse])
async def list_lora_series(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[LoraSeriesResponse]:
    series_records = list(
        await session.scalars(
            select(LoraSeries)
            .options(selectinload(LoraSeries.members))
            .order_by(LoraSeries.display_name)
        )
    )
    return [LoraSeriesResponse.model_validate(series) for series in series_records]


@router.patch(
    "/lora-series/{series_id}",
    response_model=LoraSeriesResponse,
)
async def update_lora_series(
    series_id: UUID,
    request: LoraSeriesUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> LoraSeriesResponse:
    series = await session.scalar(
        select(LoraSeries)
        .options(selectinload(LoraSeries.members))
        .where(LoraSeries.id == series_id)
    )
    if series is None:
        raise ApiError(
            status_code=404,
            code="LORA_SERIES_NOT_FOUND",
            message="The LoRA training series was not found.",
        )
    series.display_name = request.display_name.strip()
    series.source = "manual"
    series.correction_state = "corrected"
    await session.commit()
    return LoraSeriesResponse.model_validate(series)


@router.patch(
    "/lora-series-members/{member_id}",
    response_model=LoraSeriesMemberResponse,
)
async def update_lora_series_member(
    member_id: UUID,
    request: LoraSeriesMemberUpdateRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> LoraSeriesMemberResponse:
    member = await _get_or_404(
        session,
        LoraSeriesMember,
        member_id,
        code="LORA_SERIES_MEMBER_NOT_FOUND",
        message="The LoRA series member was not found.",
    )
    member = await update_series_member(
        session,
        member=member,
        training_step=request.training_step,
    )
    return LoraSeriesMemberResponse.model_validate(member)


@router.post(
    "/lora-series/{series_id}/merge",
    response_model=LoraSeriesResponse,
)
async def merge_lora_series_records(
    series_id: UUID,
    request: LoraSeriesMergeRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> LoraSeriesResponse:
    target = await _get_or_404(
        session,
        LoraSeries,
        series_id,
        code="LORA_SERIES_NOT_FOUND",
        message="The target LoRA training series was not found.",
    )
    source_ids = set(request.source_series_ids) - {series_id}
    sources = list(await session.scalars(select(LoraSeries).where(LoraSeries.id.in_(source_ids))))
    if len(sources) != len(source_ids):
        raise ApiError(
            status_code=404,
            code="LORA_SERIES_NOT_FOUND",
            message="One or more source LoRA training series were not found.",
        )
    try:
        await merge_lora_series(session, target=target, sources=sources)
    except IngestionError as error:
        raise _registry_api_error(error) from error
    return await _load_lora_series_response(session, target.id)


@router.post(
    "/lora-series/{series_id}/split",
    response_model=LoraSeriesResponse,
    status_code=status.HTTP_201_CREATED,
)
async def split_lora_series_record(
    series_id: UUID,
    request: LoraSeriesSplitRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> LoraSeriesResponse:
    source = await _get_or_404(
        session,
        LoraSeries,
        series_id,
        code="LORA_SERIES_NOT_FOUND",
        message="The source LoRA training series was not found.",
    )
    try:
        new_series = await split_lora_series(
            session,
            source=source,
            member_ids=request.member_ids,
            opaque_name=request.opaque_name.strip(),
            display_name=request.display_name.strip(),
        )
    except IngestionError as error:
        raise _registry_api_error(error) from error
    return await _load_lora_series_response(session, new_series.id)


@router.get(
    "/comparison-groups",
    response_model=list[ComparisonGroupResponse],
)
async def list_comparison_groups(
    _principal: PrincipalDep,
    session: DbSessionDep,
) -> list[ComparisonGroupResponse]:
    groups = list(
        await session.scalars(
            select(ComparisonGroup)
            .options(
                selectinload(ComparisonGroup.members).selectinload(ComparisonGroupMember.artifact)
            )
            .order_by(ComparisonGroup.name)
        )
    )
    return [_comparison_group_response(group) for group in groups]


@router.post(
    "/comparison-groups",
    response_model=ComparisonGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison_group(
    request: ComparisonGroupRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ComparisonGroupResponse:
    if await session.scalar(
        select(ComparisonGroup.id).where(ComparisonGroup.name == request.name.strip())
    ):
        raise ApiError(
            status_code=409,
            code="COMPARISON_GROUP_NAME_EXISTS",
            message="A comparison group with this name already exists.",
        )
    artifacts = await _get_artifacts(session, request.artifact_ids)
    group = ComparisonGroup(
        name=request.name.strip(),
        description=request.description,
        enabled=request.enabled,
    )
    session.add(group)
    await session.flush()
    session.add_all(
        [
            ComparisonGroupMember(group_id=group.id, artifact_id=artifact.id)
            for artifact in artifacts
        ]
    )
    await session.commit()
    return await _load_comparison_group_response(session, group.id)


@router.patch(
    "/comparison-groups/{group_id}",
    response_model=ComparisonGroupResponse,
)
async def update_comparison_group(
    group_id: UUID,
    request: ComparisonGroupRequest,
    _principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ComparisonGroupResponse:
    group = await _get_or_404(
        session,
        ComparisonGroup,
        group_id,
        code="COMPARISON_GROUP_NOT_FOUND",
        message="The comparison group was not found.",
    )
    duplicate_id = await session.scalar(
        select(ComparisonGroup.id).where(
            ComparisonGroup.name == request.name.strip(),
            ComparisonGroup.id != group.id,
        )
    )
    if duplicate_id is not None:
        raise ApiError(
            status_code=409,
            code="COMPARISON_GROUP_NAME_EXISTS",
            message="A comparison group with this name already exists.",
        )
    artifacts = await _get_artifacts(session, request.artifact_ids)
    group.name = request.name.strip()
    group.description = request.description
    group.enabled = request.enabled
    await session.execute(
        delete(ComparisonGroupMember).where(ComparisonGroupMember.group_id == group.id)
    )
    await session.flush()
    session.add_all(
        [
            ComparisonGroupMember(group_id=group.id, artifact_id=artifact.id)
            for artifact in artifacts
        ]
    )
    await session.commit()
    return await _load_comparison_group_response(session, group.id)


async def _create_sync(
    session: AsyncSession,
    *,
    registry_kind: str,
    source_url: str,
    options: dict[str, object],
    progress_total: int,
) -> RegistrySyncCreatedResponse:
    active = await session.scalar(
        select(RegistrySyncRun)
        .where(
            RegistrySyncRun.registry_kind == registry_kind,
            RegistrySyncRun.status.in_({"queued", "running"}),
        )
        .order_by(RegistrySyncRun.created_at.desc())
        .limit(1)
    )
    if active is not None:
        raise ApiError(
            status_code=409,
            code="REGISTRY_SYNC_ACTIVE",
            message=f"A {registry_kind} registry synchronization is already active.",
            details={"sync_run_id": str(active.id)},
        )
    sync_run = RegistrySyncRun(
        registry_kind=registry_kind,
        source_url=source_url,
        requested_options=options,
    )
    session.add(sync_run)
    await session.flush()
    job = Job(
        kind="registry_sync",
        queue="registry",
        resource_type="registry_sync_run",
        resource_id=sync_run.id,
        progress_total=progress_total,
    )
    session.add(job)
    await session.commit()
    await session.refresh(sync_run)
    await session.refresh(job)
    try:
        enqueue_registry_sync(sync_run_id=str(sync_run.id), job_id=str(job.id))
    except Exception as exc:
        await _mark_sync_queue_failure(session, sync_run, job)
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="Registry synchronization could not be queued.",
        ) from exc
    return RegistrySyncCreatedResponse(
        sync_run=RegistrySyncRunResponse.model_validate(sync_run),
        job=JobResponse.model_validate(job),
    )


async def _create_resolution_job(
    session: AsyncSession,
    *,
    reprocess_workflows: bool,
) -> Job:
    sync_run = RegistrySyncRun(
        registry_kind="resolution",
        source_url="offline-cache",
        requested_options={"reprocess_workflows": reprocess_workflows},
    )
    session.add(sync_run)
    await session.flush()
    job = Job(
        kind="registry_sync",
        queue="registry",
        resource_type="registry_sync_run",
        resource_id=sync_run.id,
        progress_total=2 if reprocess_workflows else 1,
    )
    session.add(job)
    await session.commit()
    try:
        enqueue_registry_sync(sync_run_id=str(sync_run.id), job_id=str(job.id))
    except Exception as exc:
        await _mark_sync_queue_failure(session, sync_run, job)
        raise ApiError(
            status_code=503,
            code="QUEUE_UNAVAILABLE",
            message="Registry re-resolution could not be queued.",
        ) from exc
    await session.refresh(job)
    return job


async def _mark_sync_queue_failure(
    session: AsyncSession,
    sync_run: RegistrySyncRun,
    job: Job,
) -> None:
    now = datetime.now(UTC)
    sync_run.status = "failed"
    sync_run.error_code = "QUEUE_UNAVAILABLE"
    sync_run.error_message = "Registry synchronization could not be queued."
    sync_run.completed_at = now
    job.status = "failed"
    job.error_code = "QUEUE_UNAVAILABLE"
    job.error_message = sync_run.error_message
    job.error_details = {"retryable": True}
    job.completed_at = now
    await session.commit()


def _source_url(requested: str | None, settings: Settings) -> str:
    value = requested or settings.comfyui_base_url
    if value is None:
        raise ApiError(
            status_code=422,
            code="COMFYUI_URL_REQUIRED",
            message="Provide a ComfyUI base URL or configure CG_COMFYUI_BASE_URL.",
        )
    try:
        return normalize_comfyui_url(value)
    except IngestionError as error:
        raise _registry_api_error(error) from error


def _registry_api_error(error: IngestionError) -> ApiError:
    return ApiError(
        status_code=422,
        code=error.code,
        message=error.message,
        details=error.details,
    )


async def _get_or_404[T](
    session: AsyncSession,
    model: type[T],
    entity_id: UUID,
    *,
    code: str,
    message: str,
) -> T:
    entity = await session.get(model, entity_id)
    if entity is None:
        raise ApiError(status_code=404, code=code, message=message)
    return entity


async def _get_artifacts(
    session: AsyncSession,
    artifact_ids: list[UUID],
) -> list[ModelArtifact]:
    if not artifact_ids:
        return []
    artifacts = list(
        await session.scalars(select(ModelArtifact).where(ModelArtifact.id.in_(set(artifact_ids))))
    )
    if len(artifacts) != len(set(artifact_ids)):
        raise ApiError(
            status_code=404,
            code="MODEL_ARTIFACT_NOT_FOUND",
            message="One or more comparison-group model artifacts were not found.",
        )
    by_id = {artifact.id: artifact for artifact in artifacts}
    return [by_id[artifact_id] for artifact_id in dict.fromkeys(artifact_ids)]


async def _load_comparison_group_response(
    session: AsyncSession,
    group_id: UUID,
) -> ComparisonGroupResponse:
    group = await session.scalar(
        select(ComparisonGroup)
        .options(selectinload(ComparisonGroup.members).selectinload(ComparisonGroupMember.artifact))
        .where(ComparisonGroup.id == group_id)
    )
    if group is None:
        raise ApiError(
            status_code=404,
            code="COMPARISON_GROUP_NOT_FOUND",
            message="The comparison group was not found.",
        )
    return _comparison_group_response(group)


async def _load_lora_series_response(
    session: AsyncSession,
    series_id: UUID,
) -> LoraSeriesResponse:
    series = await session.scalar(
        select(LoraSeries)
        .options(selectinload(LoraSeries.members))
        .where(LoraSeries.id == series_id)
    )
    if series is None:
        raise ApiError(
            status_code=404,
            code="LORA_SERIES_NOT_FOUND",
            message="The LoRA training series was not found.",
        )
    return LoraSeriesResponse.model_validate(series)


def _comparison_group_response(group: ComparisonGroup) -> ComparisonGroupResponse:
    return ComparisonGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        enabled=group.enabled,
        created_at=group.created_at,
        updated_at=group.updated_at,
        members=[
            ComparisonGroupMemberResponse(
                artifact_id=member.artifact.id,
                display_name=member.artifact.display_name,
                artifact_type=member.artifact.artifact_type,
                architecture_family=member.artifact.architecture_family,
                lineage=member.artifact.lineage,
            )
            for member in group.members
        ],
    )
