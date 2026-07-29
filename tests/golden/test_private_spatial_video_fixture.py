from __future__ import annotations

import os
from pathlib import Path

import pytest

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.files import probe_media
from comfy_gallery_core.media.spatial_video import validate_spatial_video

SOURCE_ENV = "CG_PRIVATE_SPATIAL_SOURCE"
VARIANT_ENV = "CG_PRIVATE_SPATIAL_VARIANT"


def test_private_apple_spatial_video_fixture_validates_end_to_end() -> None:
    source_path = _fixture_path(SOURCE_ENV)
    variant_path = _fixture_path(VARIANT_ENV)
    if source_path is None or variant_path is None:
        pytest.skip(f"Set both {SOURCE_ENV} and {VARIANT_ENV} to run the private MV-HEVC fixture.")

    settings = Settings(environment="test")
    source_probe = probe_media(source_path, settings)
    variant_probe = probe_media(variant_path, settings)

    result = validate_spatial_video(
        variant_path,
        probe=variant_probe,
        original_duration_seconds=source_probe.duration_seconds,
        settings=settings,
    )

    assert source_probe.signature.kind == "video"
    assert variant_probe.video_codec == "hevc"
    assert variant_probe.signature.mime_type == "video/quicktime"
    assert variant_probe.signature.normalized_extension == "mov"
    assert result.evidence["profile"] == "apple-mv-hevc-spatial-v1"
    assert result.evidence["primary_view_decoded"] is True
    assert result.evidence["secondary_view_decoded"] is True
    assert result.evidence["duration_delta_seconds"] == pytest.approx(0, abs=0.001)


def _fixture_path(environment_name: str) -> Path | None:
    configured = os.environ.get(environment_name)
    if not configured:
        return None
    path = Path(configured).expanduser().resolve()
    if not path.is_file():
        pytest.fail(f"{environment_name} does not point to a file: {path}")
    return path
