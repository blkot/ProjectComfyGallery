from datetime import UTC, datetime
from uuid import UUID

from comfy_gallery_api.media_schemas import UploadBatchResponse


def test_upload_batch_response_exposes_follow_up_urls() -> None:
    batch_id = UUID("019fcf00-0000-7000-8000-000000000001")
    item_id = UUID("019fcf00-0000-7000-8000-000000000002")
    media_id = UUID("019fcf00-0000-7000-8000-000000000003")
    created_at = datetime(2026, 8, 5, tzinfo=UTC)

    response = UploadBatchResponse.model_validate(
        {
            "id": batch_id,
            "status": "completed",
            "total_count": 1,
            "queued_count": 0,
            "completed_count": 1,
            "duplicate_count": 0,
            "failed_count": 0,
            "created_at": created_at,
            "completed_at": created_at,
            "items": [
                {
                    "id": item_id,
                    "batch_id": batch_id,
                    "media_id": media_id,
                    "original_filename": "source.mov",
                    "byte_size": 1024,
                    "status": "completed",
                    "error_code": None,
                    "error_message": None,
                    "created_at": created_at,
                    "completed_at": created_at,
                }
            ],
        }
    ).model_dump(mode="json")

    assert response["status_url"] == f"/api/v1/imports/{batch_id}"
    assert response["items"][0]["media_url"] == f"/api/v1/media/{media_id}"
    assert response["items"][0]["variant_import_url"] == (
        f"/api/v1/media/{media_id}/variant-imports"
    )


def test_unresolved_upload_item_does_not_invent_media_urls() -> None:
    batch_id = UUID("019fcf00-0000-7000-8000-000000000011")
    created_at = datetime(2026, 8, 5, tzinfo=UTC)

    response = UploadBatchResponse.model_validate(
        {
            "id": batch_id,
            "status": "processing",
            "total_count": 1,
            "queued_count": 1,
            "completed_count": 0,
            "duplicate_count": 0,
            "failed_count": 0,
            "created_at": created_at,
            "completed_at": None,
            "items": [
                {
                    "id": UUID("019fcf00-0000-7000-8000-000000000012"),
                    "batch_id": batch_id,
                    "media_id": None,
                    "original_filename": "source.mov",
                    "byte_size": 1024,
                    "status": "queued",
                    "error_code": None,
                    "error_message": None,
                    "created_at": created_at,
                    "completed_at": None,
                }
            ],
        }
    ).model_dump(mode="json")

    assert response["status_url"] == f"/api/v1/imports/{batch_id}"
    assert response["items"][0]["media_id"] is None
    assert response["items"][0]["media_url"] is None
    assert response["items"][0]["variant_import_url"] is None
