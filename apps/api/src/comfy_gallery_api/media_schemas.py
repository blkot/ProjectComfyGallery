from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceRootCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    path: str = Field(min_length=1, max_length=1024)


class SourceRootUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    enabled: bool | None = None


class SourceRootResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    path: str
    enabled: bool
    last_scan_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ScanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_root_id: UUID
    status: str
    discovered_count: int
    skipped_count: int
    imported_count: int
    duplicate_count: int
    failed_count: int
    missing_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    queue: str
    status: str
    resource_type: str
    resource_id: UUID
    stage: str | None
    attempt_count: int
    progress_current: int
    progress_total: int
    cancel_requested: bool
    error_code: str | None
    error_message: str | None
    error_details: dict[str, object]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class UploadItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_id: UUID
    media_id: UUID | None
    original_filename: str
    byte_size: int
    status: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class UploadBatchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    total_count: int
    queued_count: int
    completed_count: int
    duplicate_count: int
    failed_count: int
    created_at: datetime
    completed_at: datetime | None
    items: list[UploadItemResponse] = Field(default_factory=list)


class DerivativeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: str
    recipe_version: str
    mime_type: str
    byte_size: int
    width: int | None
    height: int | None
    container: str | None
    codec: str | None


class SourceOccurrenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_root_id: UUID
    relative_path: str
    original_filename: str
    byte_size: int
    mtime_ns: int
    sha256: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    superseded_at: datetime | None
    error_code: str | None
    error_message: str | None


class MediaListItemResponse(BaseModel):
    id: UUID
    kind: str
    status: str
    detected_format: str | None
    mime_type: str | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    container: str | None
    video_codec: str | None
    warning_count: int
    byte_size: int
    original_filename: str
    source_count: int
    workflow_status: str
    evaluation_state: str
    is_trash: bool
    file_created_at: datetime
    created_at: datetime
    preview_url: str


class MediaPageResponse(BaseModel):
    items: list[MediaListItemResponse]
    total: int
    limit: int
    offset: int


class MediaNavigationResponse(BaseModel):
    media_id: UUID
    position: int
    total: int
    previous_id: UUID | None
    previous_position: int | None
    next_id: UUID | None
    next_position: int | None


class MediaDetailResponse(BaseModel):
    id: UUID
    kind: str
    status: str
    detected_format: str | None
    mime_type: str | None
    width: int | None
    height: int | None
    duration_seconds: float | None
    frame_rate: float | None
    container: str | None
    video_codec: str | None
    audio_codec: str | None
    probe_data: dict[str, object]
    warning_count: int
    last_error_code: str | None
    last_error_message: str | None
    sha256: str
    byte_size: int
    original_filename: str
    original_extension: str | None
    file_created_at: datetime
    created_at: datetime
    updated_at: datetime
    preview_url: str
    playback_url: str
    original_url: str
    workflow_url: str
    workflow_status: str
    evaluation_state: str
    is_trash: bool
    derivatives: list[DerivativeResponse]
    sources: list[SourceOccurrenceResponse]


class WorkflowValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    locator: str
    input_name: str | None
    input_index: int | None
    value_kind: str
    raw_value: Any
    normalized_text: str | None


class WorkflowNodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_definition_id: UUID | None
    definition_match_state: str
    definition_confidence: float | None
    representation: str
    ordinal: int
    original_node_id: str
    class_type: str
    title: str | None
    module_hint: str | None
    mode: int | None
    raw_properties: dict[str, Any]
    raw_widgets: list[Any]
    raw_inputs: dict[str, Any] | list[Any]
    values: list[WorkflowValueResponse]


class WorkflowEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    representation: str
    ordinal: int
    original_link_id: str | None
    source_node_id: str
    source_output_index: int | None
    destination_node_id: str
    destination_input_index: int | None
    destination_input_name: str | None
    declared_type: str | None
    raw_link: dict[str, Any] | list[Any]


class SemanticObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    node_id: UUID | None
    observation_type: str
    role: str | None
    value: Any
    confidence: float
    correction_state: str
    evidence: dict[str, Any]
    created_at: datetime


class ExtractionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    extractor_name: str
    extractor_version: str
    graph_version: str
    configuration_hash: str
    reason: str
    status: str
    is_current: bool
    observation_count: int
    started_at: datetime
    completed_at: datetime | None
    error_code: str | None
    error_message: str | None


class WorkflowModelUsageResponse(BaseModel):
    id: UUID
    node_id: UUID | None
    model_reference_id: UUID
    artifact_id: UUID | None
    observation_type: str
    raw_reference: str
    artifact_display_name: str | None
    architecture_family: str | None
    lineage: str | None
    pipeline_pattern: str
    slot: str
    usage_order: int
    confidence: float
    correction_state: str
    evidence: dict[str, Any]


class WorkflowSnapshotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_id: UUID
    reader_name: str
    reader_version: str
    source_carrier: str
    evidence_sha256: str
    api_prompt_status: str
    visual_workflow_status: str
    parse_status: str
    issue_details: dict[str, Any]
    error_code: str | None
    error_message: str | None
    graph_version: str | None
    api_node_count: int
    visual_node_count: int
    edge_count: int
    created_at: datetime


class WorkflowDetailResponse(BaseModel):
    media_id: UUID
    status: str
    snapshot: WorkflowSnapshotResponse | None
    nodes: list[WorkflowNodeResponse] = Field(default_factory=list)
    edges: list[WorkflowEdgeResponse] = Field(default_factory=list)
    observations: list[SemanticObservationResponse] = Field(default_factory=list)
    model_usages: list[WorkflowModelUsageResponse] = Field(default_factory=list)
    runs: list[ExtractionRunResponse] = Field(default_factory=list)
    node_limit: int
    node_offset: int
    nodes_truncated: bool
    edges_truncated: bool
    raw_url: str | None


class WorkflowRawEvidenceResponse(BaseModel):
    snapshot_id: UUID
    evidence_sha256: str
    raw_metadata: dict[str, Any]
    raw_api_prompt_text: str | None
    raw_visual_workflow_text: str | None
    api_prompt: dict[str, Any] | None
    visual_workflow: dict[str, Any] | None


class WorkflowBulkReprocessRequest(BaseModel):
    mode: Literal["missing", "all"] = "missing"


class WorkflowBulkReprocessResponse(BaseModel):
    mode: str
    matched_count: int
    queued_count: int
    already_active_count: int
    queue_failed_count: int
    job_ids: list[UUID]
