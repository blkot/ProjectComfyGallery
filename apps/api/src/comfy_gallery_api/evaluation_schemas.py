from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CriterionResponse(BaseModel):
    criterion_version_id: UUID
    stable_key: str
    module: str
    version: int
    label: str
    guidance: str
    anchor_0: str
    anchor_5: str
    anchor_10: str
    required: bool
    allow_na: bool


class ScoreResponse(BaseModel):
    criterion_version_id: UUID
    state: str
    value: int | None
    na_reason: str | None
    updated_at: datetime


class EvaluationResponse(BaseModel):
    id: UUID
    media_id: UUID
    template_id: UUID
    template_name: str
    template_version: int
    module: str
    evaluation_kind: str
    progress_state: str
    is_trash: bool
    version: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    criteria: list[CriterionResponse]
    scores: list[ScoreResponse]


class EvaluationTemplateResponse(BaseModel):
    id: UUID
    stable_key: str
    version: int
    name: str
    media_kind: str
    module: str
    locked: bool
    criteria: list[CriterionResponse]


class ScoreUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)
    state: Literal["scored", "na"]
    value: int | None = Field(default=None, ge=0, le=10)
    na_reason: str | None = Field(default=None, max_length=1024)


class ScoreClearRequest(BaseModel):
    expected_version: int = Field(ge=1)


class TrashUpdateRequest(BaseModel):
    expected_version: int = Field(ge=1)


class ScoreRevisionResponse(BaseModel):
    id: UUID
    criterion_version_id: UUID
    criterion_key: str
    old_state: str
    old_value: int | None
    new_state: str
    new_value: int | None
    evaluation_version: int
    created_at: datetime


class DispositionRevisionResponse(BaseModel):
    id: UUID
    old_is_trash: bool
    new_is_trash: bool
    evaluation_version: int
    created_at: datetime


class EvaluationRevisionsResponse(BaseModel):
    scores: list[ScoreRevisionResponse]
    dispositions: list[DispositionRevisionResponse]


class MediaFilterRequest(BaseModel):
    kind: Literal["image", "video"] | None = None
    status: str | None = None
    workflow_status: str | None = None
    evaluation_state: Literal["not_started", "in_progress", "complete"] | None = None
    trash: bool | None = None
    spatial_view_preferred: bool | None = None
    favorite: bool | None = None
    source_root_id: UUID | None = None
    # Singular fields keep saved filters created before multi-reference support valid.
    checkpoint_reference_id: UUID | None = None
    lora_reference_id: UUID | None = None
    checkpoint_reference_ids: list[UUID] = Field(default_factory=list, max_length=100)
    checkpoint_reference_match: Literal["any", "all"] = "any"
    lora_reference_ids: list[UUID] = Field(default_factory=list, max_length=100)
    lora_reference_match: Literal["any", "all"] = "any"
    collection_id: UUID | None = None
    tag_id: UUID | None = None

    def checkpoint_ids(self) -> list[UUID]:
        values = [self.checkpoint_reference_id] if self.checkpoint_reference_id is not None else []
        return list(dict.fromkeys([*values, *self.checkpoint_reference_ids]))

    def lora_ids(self) -> list[UUID]:
        values = [self.lora_reference_id] if self.lora_reference_id is not None else []
        return list(dict.fromkeys([*values, *self.lora_reference_ids]))


class ReviewSessionCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=256)
    source_kind: Literal[
        "random",
        "selection",
        "filter",
        "saved_filter",
        "collection",
        "source",
        "in_progress",
    ]
    media_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    collection_id: UUID | None = None
    saved_filter_id: UUID | None = None
    source_root_id: UUID | None = None
    filter: MediaFilterRequest | None = None
    random_limit: int = Field(default=100, ge=1, le=2000)
    ordering_mode: Literal["stable", "random"] = "stable"
    random_seed: int | None = None
    optional_modules: list[Literal["character"]] = Field(default_factory=list)


class ReviewSessionUpdateRequest(BaseModel):
    current_cursor: int | None = Field(default=None, ge=0)
    status: Literal["active", "finished", "abandoned"] | None = None


class ReviewSessionResponse(BaseModel):
    id: UUID
    name: str | None
    source_kind: str
    scope_snapshot: dict[str, object]
    ordering_mode: str
    random_seed: int | None
    optional_modules: list[str]
    status: str
    current_cursor: int
    candidate_count: int
    progress_counts: dict[str, int]
    last_opened_at: datetime
    created_at: datetime
    updated_at: datetime


class ReviewPromptResponse(BaseModel):
    role: str | None
    label: str
    text: str


class MediaEvaluationModuleUpdateRequest(BaseModel):
    enabled: bool


class MediaEvaluationModuleResponse(BaseModel):
    module: str
    label: str
    required: bool
    enabled: bool
    has_saved_scores: bool
    progress_state: Literal["not_started", "in_progress", "complete"] | None


class MediaEvaluationContextResponse(BaseModel):
    media_id: UUID
    progress_state: Literal["not_started", "in_progress", "complete"]
    is_trash: bool
    enabled_modules: list[str]
    available_modules: list[MediaEvaluationModuleResponse]
    prompts: list[ReviewPromptResponse]
    evaluations: list[EvaluationResponse]


class ReviewMediaResponse(BaseModel):
    id: UUID
    kind: str
    preview_url: str
    playback_url: str
    width: int | None
    height: int | None
    duration_seconds: float | None


class ReviewItemResponse(BaseModel):
    session: ReviewSessionResponse
    position: int
    media: ReviewMediaResponse
    prompts: list[ReviewPromptResponse]
    evaluations: list[EvaluationResponse]


class ReviewSummaryResponse(BaseModel):
    not_started_count: int
    in_progress_count: int
    complete_count: int
    trash_count: int
    active_session_count: int


class NamedRecordRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    item_count: int
    created_at: datetime
    updated_at: datetime


class MediaMembershipRequest(BaseModel):
    media_ids: list[UUID] = Field(default_factory=list, max_length=2000)
    filter: MediaFilterRequest | None = None

    @model_validator(mode="after")
    def require_one_scope(self) -> "MediaMembershipRequest":
        if bool(self.media_ids) == (self.filter is not None):
            raise ValueError("Provide either media_ids or filter.")
        return self


class TagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    color: str | None = Field(default=None, max_length=32)


class TagResponse(BaseModel):
    id: UUID
    name: str
    color: str | None
    item_count: int
    created_at: datetime
    updated_at: datetime


class SavedFilterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    expression: MediaFilterRequest


class SavedFilterResponse(BaseModel):
    id: UUID
    name: str
    expression: dict[str, object]
    version: int
    created_at: datetime
    updated_at: datetime
