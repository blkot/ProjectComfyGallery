from pathlib import Path
from subprocess import CompletedProcess

import pytest

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import MediaSignature, ProbeResult
from comfy_gallery_core.media.spatial_video import validate_spatial_video


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        minimum_free_bytes=0,
    )


def _probe(*, side_data: list[dict[str, object]], codec: str = "hevc") -> ProbeResult:
    return ProbeResult(
        signature=MediaSignature(
            kind="video",
            detected_format="mp4",
            mime_type="video/mp4",
            normalized_extension="mp4",
        ),
        width=1920,
        height=1080,
        duration_seconds=8.4,
        frame_rate=30,
        container="mov,mp4,m4a,3gp,3g2,mj2",
        video_codec=codec,
        raw={
            "streams": [
                {
                    "codec_type": "video",
                    "side_data_list": side_data,
                }
            ]
        },
    )


def test_valid_spatial_video_requires_metadata_and_decodes_both_views(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    decoded_views: list[int] = []

    def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        if "decoder=hevc" in command:
            return CompletedProcess(
                command,
                0,
                stdout="view_ids view_ids_available view_pos_available",
                stderr="",
            )
        mapping = command[command.index("-map") + 1]
        decoded_views.append(int(mapping.rsplit(":", 1)[1]))
        return CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("comfy_gallery_core.media.spatial_video.subprocess.run", fake_run)
    source = tmp_path / "spatial.mov"
    source.write_bytes(b"fixture bytes are not read by the bounded subprocess stub")

    result = validate_spatial_video(
        source,
        probe=_probe(
            side_data=[
                {
                    "side_data_type": "Stereo 3D",
                    "type": "unspecified",
                    "view": "packed",
                    "primary_eye": "none",
                    "baseline": 64_000,
                    "horizontal_field_of_view": "80000/1000",
                    "horizontal_disparity_adjustment": 0,
                }
            ]
        ),
        original_duration_seconds=8.5,
        settings=_settings(tmp_path),
    )

    assert decoded_views == [0, 1]
    assert result.evidence["profile"] == "apple-mv-hevc-spatial-v1"
    assert result.evidence["secondary_view_decoded"] is True
    assert result.evidence["duration_delta_seconds"] == pytest.approx(0.1)
    metadata = result.evidence["apple_spatial_metadata"]
    assert isinstance(metadata, dict)
    assert metadata["primary_eye"] == "none"
    assert metadata["horizontal_field_of_view"] == "80000/1000"


@pytest.mark.parametrize(
    ("probe", "expected_code"),
    [
        (_probe(side_data=[], codec="h264"), "VARIANT_INVALID_CODEC"),
        (_probe(side_data=[]), "VARIANT_SPATIAL_METADATA_MISSING"),
        (
            _probe(
                side_data=[
                    {
                        "side_data_type": "Stereo 3D",
                        "primary_eye": "left",
                        "baseline": 63,
                    }
                ]
            ),
            "VARIANT_SPATIAL_METADATA_MISSING",
        ),
    ],
)
def test_invalid_codec_or_incomplete_spatial_metadata_fails_closed(
    tmp_path: Path,
    probe: ProbeResult,
    expected_code: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "comfy_gallery_core.media.spatial_video._ensure_mv_hevc_validator_available",
        lambda _settings: None,
    )
    with pytest.raises(IngestionError) as raised:
        validate_spatial_video(
            tmp_path / "candidate.mov",
            probe=probe,
            original_duration_seconds=8.4,
            settings=_settings(tmp_path),
        )

    assert raised.value.code == expected_code


def test_spatial_video_duration_uses_explicit_absolute_or_relative_tolerance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "comfy_gallery_core.media.spatial_video._ensure_mv_hevc_validator_available",
        lambda _settings: None,
    )
    with pytest.raises(IngestionError) as raised:
        validate_spatial_video(
            tmp_path / "candidate.mov",
            probe=_probe(side_data=[]),
            original_duration_seconds=10.0,
            settings=_settings(tmp_path),
        )

    assert raised.value.code == "VARIANT_DURATION_MISMATCH"
    assert raised.value.details["duration_tolerance_seconds"] == 0.5


def test_missing_mv_hevc_runtime_capability_has_distinct_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        return CompletedProcess(command, 0, stdout="ordinary HEVC decoder", stderr="")

    monkeypatch.setattr("comfy_gallery_core.media.spatial_video.subprocess.run", fake_run)

    with pytest.raises(IngestionError) as raised:
        validate_spatial_video(
            tmp_path / "candidate.mov",
            probe=_probe(side_data=[]),
            original_duration_seconds=8.4,
            settings=_settings(tmp_path),
        )

    assert raised.value.code == "VARIANT_VALIDATOR_UNAVAILABLE"
    assert raised.value.details["missing_capabilities"] == [
        "view_ids",
        "view_ids_available",
    ]
