from typing import Literal

from sqlalchemy import and_, func, select
from sqlalchemy.sql import ColumnElement

from comfy_gallery_core.db.models import Media, MediaSafetyAssessment, MediaSafetyReview

ClassifierStatus = Literal[
    "unclassified",
    "suggested",
    "needs_review",
    "reviewed",
    "processing",
    "failed",
]
ClassifierRating = Literal["safe", "sexy", "nudity", "explicit", "review"]


def classifier_status_filter(value: ClassifierStatus) -> ColumnElement[bool]:
    has_review = Media.safety_review.has()
    if value == "reviewed":
        return has_review

    no_review = ~has_review
    if value == "unclassified":
        return and_(no_review, ~Media.safety_assessment.has())
    if value == "suggested":
        return and_(
            no_review,
            Media.safety_assessment.has(
                and_(
                    MediaSafetyAssessment.status == "completed",
                    MediaSafetyAssessment.needs_review.is_(False),
                )
            ),
        )
    if value == "needs_review":
        return and_(
            no_review,
            Media.safety_assessment.has(
                and_(
                    MediaSafetyAssessment.status == "completed",
                    MediaSafetyAssessment.needs_review.is_(True),
                )
            ),
        )
    if value == "processing":
        return and_(
            no_review,
            Media.safety_assessment.has(MediaSafetyAssessment.status.in_(("queued", "running"))),
        )
    return and_(
        no_review,
        Media.safety_assessment.has(MediaSafetyAssessment.status == "failed"),
    )


def classifier_rating_filter(value: ClassifierRating) -> ColumnElement[bool]:
    human_rating = (
        select(MediaSafetyReview.rating)
        .where(MediaSafetyReview.media_id == Media.id)
        .scalar_subquery()
    )
    model_rating = (
        select(MediaSafetyAssessment.suggested_rating)
        .where(
            MediaSafetyAssessment.media_id == Media.id,
            MediaSafetyAssessment.status == "completed",
        )
        .scalar_subquery()
    )
    return func.coalesce(human_rating, model_rating) == value
