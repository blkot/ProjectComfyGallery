from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

PromptRegistryMaterialization = Literal["any", "materialized", "unmaterialized"]


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
    is_trash: bool
    character_lora: str | None
    content_rating: str
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


class PromptRegistryRandomResponse(PromptRegistryEntryResponse):
    prompt_id: str
    materialization: Literal["materialized", "unmaterialized"]


class PromptRegistryStatsResponse(BaseModel):
    source: str | None
    source_count: int
    registered_count: int
    materialized_count: int
    unmaterialized_count: int


class PromptRegistryCharacterLoraResponse(BaseModel):
    name: str
    media_count: int


class PromptRegistryNeighborResponse(BaseModel):
    direction: Literal["previous", "next"]
    entry: PromptRegistryEntryResponse


class PromptRegistryHeatmapItemResponse(BaseModel):
    prompt_id: str
    source: str
    index: str
    media_count: int


class PromptRegistryHeatmapResponse(BaseModel):
    items: list[PromptRegistryHeatmapItemResponse]
    total: int
    limit: int
    offset: int
    max_media_count: int
