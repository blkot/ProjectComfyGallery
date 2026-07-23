from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from comfy_gallery_api.media_schemas import JobResponse


class RegistrySyncRequest(BaseModel):
    base_url: str | None = Field(default=None, max_length=2048)


class ModelRegistrySyncRequest(RegistrySyncRequest):
    run_scans: bool = True
    fetch_civitai: bool = True


class RegistrySyncRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registry_kind: str
    source_url: str
    requested_options: dict[str, Any]
    status: str
    current_stage: str | None
    stage_status: dict[str, Any]
    counts: dict[str, Any]
    source_versions: dict[str, Any]
    node_snapshot_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class RegistrySyncCreatedResponse(BaseModel):
    sync_run: RegistrySyncRunResponse
    job: JobResponse


class NodeMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_definition_id: UUID
    locator: str
    input_name: str | None
    input_index: int | None
    semantic_type: str
    role: str | None
    source: str
    confidence: float
    state: str
    correction_state: str
    evidence: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class NodeDefinitionListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    class_type: str
    python_module: str
    schema_fingerprint: str
    source_kind: str
    display_name: str | None
    category: str | None
    is_present: bool
    mapping_state: str
    workflow_occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime


class NodeDefinitionDetailResponse(NodeDefinitionListItemResponse):
    description: str | None
    input_schema: dict[str, Any]
    output_schema: list[Any]
    raw_definition: dict[str, Any]
    mappings: list[NodeMappingResponse]


class NodeDefinitionPageResponse(BaseModel):
    items: list[NodeDefinitionListItemResponse]
    total: int
    limit: int
    offset: int


class NodeMappingCreateRequest(BaseModel):
    node_definition_id: UUID
    locator: str = Field(min_length=1, max_length=512)
    semantic_type: Literal[
        "checkpoint_reference",
        "lora_reference",
        "prompt",
        "generation_parameter",
        "ignore",
    ]
    role: str | None = Field(default=None, max_length=128)


class NodeMappingCreatedResponse(BaseModel):
    mapping: NodeMappingResponse
    job: JobResponse


class ModelArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_type: str
    display_name: str
    file_name: str | None
    file_path: str | None
    sha256: str | None
    provider: str
    provider_model_id: str | None
    provider_version_id: str | None
    provider_url: str | None
    identity_state: str
    availability: str
    enrichment_state: str
    architecture_family: str | None
    lineage: str | None
    variant: str | None
    precision: str | None
    quantization: str | None
    manual_overrides: dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class ModelArtifactDetailResponse(ModelArtifactResponse):
    raw_inventory: dict[str, Any]
    raw_provider_metadata: dict[str, Any]


class ModelArtifactPageResponse(BaseModel):
    items: list[ModelArtifactResponse]
    total: int
    limit: int
    offset: int


class ModelArtifactUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=1024)
    artifact_type: str | None = Field(default=None, min_length=1, max_length=64)
    architecture_family: str | None = Field(default=None, max_length=256)
    lineage: str | None = Field(default=None, max_length=256)
    variant: str | None = Field(default=None, max_length=256)
    precision: str | None = Field(default=None, max_length=64)
    quantization: str | None = Field(default=None, max_length=64)
    availability: Literal["present", "missing", "unknown"] | None = None


class ModelArtifactUpdatedResponse(BaseModel):
    artifact: ModelArtifactResponse
    job: JobResponse


class ModelReferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID | None
    reference_type: str
    raw_value: str
    normalized_value: str
    availability: str
    resolution_state: str
    match_method: str | None
    confidence: float | None
    occurrence_count: int
    candidate_artifact_ids: list[Any]
    manual_override: bool
    first_seen_at: datetime
    last_seen_at: datetime


class ModelReferencePageResponse(BaseModel):
    items: list[ModelReferenceResponse]
    total: int
    limit: int
    offset: int


class ModelReferenceLinkRequest(BaseModel):
    artifact_id: UUID | None


class ModelReferenceLinkedResponse(BaseModel):
    reference: ModelReferenceResponse
    job: JobResponse


class LoraSeriesMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    series_id: UUID
    model_reference_id: UUID
    artifact_id: UUID | None
    training_step: int
    source: str
    correction_state: str
    created_at: datetime
    updated_at: datetime


class LoraSeriesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    opaque_name: str
    display_name: str
    source: str
    correction_state: str
    created_at: datetime
    updated_at: datetime
    members: list[LoraSeriesMemberResponse]


class LoraSeriesUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=1024)


class LoraSeriesMemberUpdateRequest(BaseModel):
    training_step: int = Field(ge=0)


class LoraSeriesMergeRequest(BaseModel):
    source_series_ids: list[UUID] = Field(min_length=1, max_length=1000)


class LoraSeriesSplitRequest(BaseModel):
    opaque_name: str = Field(min_length=1, max_length=1024)
    display_name: str = Field(min_length=1, max_length=1024)
    member_ids: list[UUID] = Field(min_length=1, max_length=1000)


class ComparisonGroupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    enabled: bool = True
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=1000)


class ComparisonGroupMemberResponse(BaseModel):
    artifact_id: UUID
    display_name: str
    artifact_type: str
    architecture_family: str | None
    lineage: str | None


class ComparisonGroupResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    members: list[ComparisonGroupMemberResponse]
