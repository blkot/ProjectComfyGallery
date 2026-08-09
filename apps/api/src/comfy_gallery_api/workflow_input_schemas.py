from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from comfy_gallery_api.media_schemas import JobResponse


class WorkflowInputAssetResponse(BaseModel):
    id: UUID
    sha256: str
    kind: str
    detected_format: str
    mime_type: str
    byte_size: int
    width: int | None
    height: int | None
    duration_seconds: float | None
    frame_rate: float | None
    container: str | None
    video_codec: str | None
    audio_codec: str | None


class WorkflowInputReferenceResponse(BaseModel):
    id: UUID
    status: str
    representation: str
    original_node_id: str
    class_type: str
    locator: str
    input_name: str | None
    media_kind_hint: str | None
    source_filename: str
    source_subfolder: str | None
    source_type: str
    raw_value: Any
    attempt_count: int
    last_attempt_at: datetime | None
    resolved_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    resolution_details: dict[str, object]
    asset: WorkflowInputAssetResponse | None
    content_url: str | None


class WorkflowInputListResponse(BaseModel):
    media_id: UUID
    items: list[WorkflowInputReferenceResponse]
    total: int
    ready_count: int
    unresolved_count: int


class WorkflowInputResolveAcceptedResponse(BaseModel):
    media_id: UUID
    job: JobResponse
