from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from comfy_gallery_api.media_schemas import JobResponse


class SpatialConversionCreateRequest(BaseModel):
    precision: str | None = Field(default=None, max_length=64)
    spatial_quality: str | None = Field(default=None, max_length=64)
    spatial_preset: str | None = Field(default=None, max_length=64)

    @field_validator("precision", "spatial_quality", "spatial_preset")
    @classmethod
    def normalize_option(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SpatialConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_id: UUID
    status: str
    requested_options: dict[str, object]
    mss_batch_id: str | None
    queue_position: int | None
    mss_file_status: str | None
    publish_status: str | None
    gallery_media_id: UUID | None
    gallery_variant_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    submitted_at: datetime | None
    completed_at: datetime | None


class SpatialConversionStateResponse(BaseModel):
    configured: bool
    conversion: SpatialConversionResponse | None
    job: JobResponse | None
