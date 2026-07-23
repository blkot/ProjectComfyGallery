from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReportType = Literal[
    "checkpoint",
    "checkpoint_pair",
    "lora",
    "lora_training_series",
    "checkpoint_lora_matrix",
    "lora_combination",
]


class AnalysisFilterRequest(BaseModel):
    module: Literal["core", "character"] = "core"
    media_kind: Literal["image", "video"] | None = None
    template_ids: list[UUID] = Field(default_factory=list, max_length=100)
    collection_id: UUID | None = None
    tag_id: UUID | None = None
    source_root_id: UUID | None = None
    architecture_family: str | None = Field(default=None, max_length=256)
    pipeline_pattern: str | None = Field(default=None, max_length=80)
    slots: list[str] = Field(default_factory=list, max_length=50)
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=1000)
    comparison_group_id: UUID | None = None
    lora_series_id: UUID | None = None
    include_trash: bool = False


class AnalysisSpecRequest(BaseModel):
    report_type: ReportType = "checkpoint"
    criterion_keys: list[str] = Field(default_factory=list, max_length=100)
    compatibility_mode: Literal["shared", "available"] = "shared"
    any_role: bool = False
    reference_group_key: str | None = Field(default=None, max_length=8192)
    weighting_profile_id: UUID | None = None


class AnalysisPreviewRequest(BaseModel):
    filter: AnalysisFilterRequest = Field(default_factory=AnalysisFilterRequest)
    spec: AnalysisSpecRequest = Field(default_factory=AnalysisSpecRequest)


class AnalysisRunCreateRequest(AnalysisPreviewRequest):
    title: str = Field(min_length=1, max_length=256)


class WeightingProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    weights: dict[str, float] = Field(default_factory=dict)
    default_weight: float = Field(default=1.0, ge=0, le=100)


class WeightingProfileVersionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    weights: dict[str, float] = Field(default_factory=dict)
    default_weight: float = Field(default=1.0, ge=0, le=100)


class WeightingProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    stable_key: str
    version: int
    name: str
    description: str | None
    weights: dict[str, Any]
    default_weight: float
    is_builtin: bool
    created_at: datetime


class AnalysisOption(BaseModel):
    id: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisOptionsResponse(BaseModel):
    templates: list[AnalysisOption]
    criteria: list[AnalysisOption]
    artifacts: list[AnalysisOption]
    comparison_groups: list[AnalysisOption]
    lora_series: list[AnalysisOption]
    architecture_families: list[str]
    pipeline_patterns: list[str]
    slots: list[str]


class AnalysisResultResponse(BaseModel):
    id: UUID | None = None
    group_key: str
    group_label: str
    dimensions: dict[str, Any]
    criterion_key: str
    criterion_label: str
    eligible_count: int
    scored_count: int
    na_count: int
    not_collected_count: int
    trash_count: int
    coverage: float
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    q1: float | None
    q3: float | None
    ci_low: float | None
    ci_high: float | None
    reference_group_key: str | None
    difference_from_reference: float | None
    effect_size: float | None
    evidence_strength: str
    histogram: list[int]
    context: dict[str, Any]


class AnalysisReportResponse(BaseModel):
    report_type: str
    media_count: int
    excluded_count: int
    group_count: int
    effective_criteria: list[dict[str, Any]]
    warnings: list[str]
    context: dict[str, Any]
    results: list[AnalysisResultResponse]


class AnalysisRunSummaryResponse(BaseModel):
    id: UUID
    title: str
    report_type: str
    status: str
    parent_run_id: UUID | None
    weighting_profile_id: UUID
    media_count: int
    excluded_count: int
    group_count: int
    warnings: list[Any]
    created_at: datetime
    completed_at: datetime | None


class AnalysisRunDetailResponse(AnalysisRunSummaryResponse):
    filter_spec: dict[str, Any]
    report_spec: dict[str, Any]
    calculation_version: str
    effective_criteria: list[Any]
    context: dict[str, Any]
    results: list[AnalysisResultResponse]


class AnalysisMediaResponse(BaseModel):
    media_id: UUID
    evaluation_id: UUID | None
    included: bool
    exclusion_reason: str | None
    composite_score: float | None
    group_keys: list[Any]
    preview_url: str
