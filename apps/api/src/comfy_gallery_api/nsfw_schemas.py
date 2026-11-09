from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from comfy_gallery_api.evaluation_schemas import MediaMembershipRequest
from comfy_gallery_api.media_schemas import JobResponse

SuggestedContentRating = Literal["safe", "sexy", "nudity", "explicit", "review"]
HumanContentRating = Literal["safe", "sexy", "nudity", "explicit"]


class MediaSafetyReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_id: UUID
    rating: HumanContentRating
    reviewer_user_id: UUID
    reviewed_at: datetime
    created_at: datetime
    updated_at: datetime


class MediaSafetyReviewUpdateRequest(BaseModel):
    rating: HumanContentRating


class MediaSafetyAssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    media_id: UUID
    job_id: UUID | None
    model_id: str
    model_revision: str
    inference_backend: str
    status: str
    label: str | None
    suggested_rating: SuggestedContentRating | None
    confidence: float | None
    margin: float | None
    scores: dict[str, object]
    needs_review: bool
    nudity_detector_status: Literal["disabled", "skipped", "completed"]
    nudity_detector_mode: Literal["disabled", "always", "risk_or_review"]
    nudity_detected: bool
    nudity_model_id: str | None
    nudity_model_revision: str | None
    nudity_detections: list[dict[str, object]]
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MediaSafetyClassificationRequest(MediaMembershipRequest):
    force: bool = False


class MediaSafetyClassificationBatchResponse(BaseModel):
    requested_count: int
    queued_count: int
    reused_count: int
    skipped_count: int
    queue_failed_count: int
    job_ids: list[UUID] = Field(default_factory=list)


class MediaSafetyClassificationStatusResponse(BaseModel):
    media_id: UUID
    assessment: MediaSafetyAssessmentResponse | None
    review: MediaSafetyReviewResponse | None = None
    job: JobResponse | None
