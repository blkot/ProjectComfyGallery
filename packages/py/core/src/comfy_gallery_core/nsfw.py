from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import MediaSafetyAssessment

NUDENET_MODEL_ID = "notAI-tech/NudeNet"


def assessment_matches_settings(
    assessment: MediaSafetyAssessment,
    settings: Settings,
) -> bool:
    """Return whether an assessment used the currently selected model configuration."""

    if (
        assessment.model_id != settings.nsfw_model_id
        or assessment.model_revision != settings.nsfw_model_revision
        or assessment.inference_backend != settings.nsfw_inference_backend
    ):
        return False
    if not settings.nsfw_nudenet_enabled:
        return (
            assessment.nudity_detector_status == "disabled"
            and assessment.nudity_detector_mode == "disabled"
            and assessment.nudity_model_id is None
            and assessment.nudity_model_revision is None
        )
    return (
        assessment.nudity_model_id == NUDENET_MODEL_ID
        and assessment.nudity_model_revision == settings.nsfw_nudenet_model_revision
        and assessment.nudity_detector_mode == settings.nsfw_nudenet_run_mode
        and assessment.nudity_detector_status in {"completed", "skipped"}
    )
