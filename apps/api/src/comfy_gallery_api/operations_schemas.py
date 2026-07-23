from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ExportCreateRequest(BaseModel):
    include_workflow_evidence: bool = True


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    export_schema_version: str
    requested_options: dict[str, object]
    sha256: str | None
    byte_size: int | None
    table_counts: dict[str, object]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    download_url: str | None = Field(default=None)


class StatusCheck(BaseModel):
    status: str
    detail: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class OperationalStatusResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict[str, StatusCheck]
    warnings: list[str] = Field(default_factory=list)
