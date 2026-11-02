from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PromptRegistryEntryRequest(BaseModel):
    source: str = Field(min_length=1, max_length=256)
    index: str = Field(min_length=1, max_length=128, pattern=r"^\d+$")
    prompt: str = Field(default="", max_length=200_000)
    negative_prompt: str | None = Field(default=None, max_length=200_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    origin: str = Field(default="xanta-utils", min_length=1, max_length=64)


class PromptRegistryEntryResponse(BaseModel):
    id: UUID
    source: str
    index: str
    prompt: str
    negative_prompt: str | None
    metadata: dict[str, Any]
    origin: str
    media_count: int = 0
    created_at: datetime
    updated_at: datetime


class PromptRegistryImportRequest(BaseModel):
    entries: list[PromptRegistryEntryRequest] = Field(min_length=1, max_length=2_000)


class PromptRegistryImportResponse(BaseModel):
    created_count: int
    updated_count: int
    entries: list[PromptRegistryEntryResponse]


class PromptRegistryPageResponse(BaseModel):
    items: list[PromptRegistryEntryResponse]
    total: int
    limit: int
    offset: int


class PromptRegistryMediaResponse(BaseModel):
    id: UUID
    kind: str
    original_filename: str
    width: int | None
    height: int | None
    duration_seconds: float | None
    favorite: bool
    content_rating: str | None
    preview_url: str
    created_at: datetime


class PromptRegistryLookupResponse(BaseModel):
    prompt_id: str
    source: str
    index: str
    entry: PromptRegistryEntryResponse | None
    media: list[PromptRegistryMediaResponse]
    total_media: int
    limit: int
    offset: int
