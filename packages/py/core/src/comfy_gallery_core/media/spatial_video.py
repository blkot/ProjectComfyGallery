from __future__ import annotations

import subprocess
from dataclasses import dataclass
from fractions import Fraction
from math import isfinite
from pathlib import Path
from typing import Any

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import ProbeResult

SPATIAL_VALIDATION_PROFILE = "apple-mv-hevc-spatial-v1"


@dataclass(frozen=True, slots=True)
class SpatialVideoValidation:
    evidence: dict[str, object]


def validate_spatial_video(
    path: Path,
    *,
    probe: ProbeResult,
    original_duration_seconds: float | None,
    settings: Settings,
) -> SpatialVideoValidation:
    """Fail closed unless both Apple spatial metadata and two HEVC views are proven."""

    if probe.signature.kind != "video" or probe.signature.detected_format != "mp4":
        raise IngestionError(
            code="VARIANT_INVALID_CONTAINER",
            message="A spatial video variant must use an MP4/QuickTime-family container.",
        )
    container_names = {
        value.strip().casefold() for value in (probe.container or "").split(",") if value.strip()
    }
    if not container_names.intersection({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}):
        raise IngestionError(
            code="VARIANT_INVALID_CONTAINER",
            message="The uploaded container is not supported for Apple spatial video.",
            details={"container": probe.container},
        )
    if (probe.video_codec or "").casefold() not in {"hevc", "h265"}:
        raise IngestionError(
            code="VARIANT_INVALID_CODEC",
            message="A spatial video variant must contain HEVC/MV-HEVC video.",
            details={"video_codec": probe.video_codec},
        )
    _ensure_mv_hevc_validator_available(settings)
    if not probe.width or not probe.height or not probe.duration_seconds:
        raise IngestionError(
            code="VARIANT_INVALID_CODEC",
            message="The spatial video must have nonzero dimensions and duration.",
        )
    if not original_duration_seconds or original_duration_seconds <= 0:
        raise IngestionError(
            code="VARIANT_DURATION_MISMATCH",
            message="The original video has no usable duration for variant validation.",
        )

    duration_delta = abs(probe.duration_seconds - original_duration_seconds)
    duration_tolerance = max(
        settings.spatial_variant_duration_tolerance_seconds,
        original_duration_seconds * settings.spatial_variant_duration_tolerance_ratio,
    )
    if duration_delta > duration_tolerance:
        raise IngestionError(
            code="VARIANT_DURATION_MISMATCH",
            message="The spatial video duration differs too much from the original.",
            details={
                "original_duration_seconds": original_duration_seconds,
                "variant_duration_seconds": probe.duration_seconds,
                "duration_delta_seconds": duration_delta,
                "duration_tolerance_seconds": duration_tolerance,
            },
        )

    stereo_data = _apple_stereo_side_data(probe.raw or {})
    if stereo_data is None:
        raise IngestionError(
            code="VARIANT_SPATIAL_METADATA_MISSING",
            message="Apple spatial stereo metadata was not found in the uploaded video.",
        )

    _decode_view(path, view_index=0, settings=settings, error_code="VARIANT_INVALID_CODEC")
    _decode_view(
        path,
        view_index=1,
        settings=settings,
        error_code="VARIANT_SPATIAL_METADATA_MISSING",
    )

    return SpatialVideoValidation(
        evidence={
            "profile": SPATIAL_VALIDATION_PROFILE,
            "container_valid": True,
            "hevc_valid": True,
            "primary_view_decoded": True,
            "secondary_view_decoded": True,
            "apple_spatial_metadata": stereo_data,
            "original_duration_seconds": original_duration_seconds,
            "variant_duration_seconds": probe.duration_seconds,
            "duration_delta_seconds": duration_delta,
            "duration_tolerance_seconds": duration_tolerance,
            "original_frame_rate_comparison_deferred": True,
        }
    )


def _ensure_mv_hevc_validator_available(settings: Settings) -> None:
    command = [
        settings.ffmpeg_path,
        "-hide_banner",
        "-h",
        "decoder=hevc",
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=settings.spatial_variant_validation_timeout_seconds,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise IngestionError(
            code="VARIANT_VALIDATOR_UNAVAILABLE",
            message="The FFmpeg MV-HEVC validator is unavailable.",
            details={"reason": str(exc)},
        ) from exc

    help_output = f"{completed.stdout}\n{completed.stderr}"
    required_options = ("view_ids", "view_ids_available")
    if not all(option in help_output for option in required_options):
        raise IngestionError(
            code="VARIANT_VALIDATOR_UNAVAILABLE",
            message="FFmpeg 7.1 or newer with MV-HEVC view decoding support is required.",
            details={
                "missing_capabilities": [
                    option for option in required_options if option not in help_output
                ]
            },
        )


def _apple_stereo_side_data(payload: dict[str, object]) -> dict[str, object] | None:
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return None
    for stream in streams:
        if not isinstance(stream, dict) or stream.get("codec_type") != "video":
            continue
        side_data_list = stream.get("side_data_list")
        if not isinstance(side_data_list, list):
            continue
        for item in side_data_list:
            if not isinstance(item, dict):
                continue
            side_data_type = str(item.get("side_data_type") or "").casefold()
            if "stereo 3d" not in side_data_type:
                continue
            baseline = _positive_number(item.get("baseline"))
            horizontal_fov = _positive_number(item.get("horizontal_field_of_view"))
            primary_eye = str(item.get("primary_eye") or "").casefold()
            if (
                baseline is None
                or horizontal_fov is None
                or primary_eye not in {"left", "right", "none"}
            ):
                continue
            return _json_safe_mapping(item)
    return None


def _decode_view(
    path: Path,
    *,
    view_index: int,
    settings: Settings,
    error_code: str,
) -> None:
    command = [
        settings.ffmpeg_path,
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        f"0:v:0:vidx:{view_index}",
        "-frames:v",
        "1",
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=settings.spatial_variant_validation_timeout_seconds,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = ""
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = exc.stderr.decode("utf-8", errors="replace")[-2000:]
        message = (
            "The HEVC video could not be decoded."
            if error_code == "VARIANT_INVALID_CODEC"
            else "A decodable secondary MV-HEVC view was not found."
        )
        raise IngestionError(
            code=error_code,
            message=message,
            details={"view_index": view_index, "reason": str(exc), "ffmpeg": stderr},
        ) from exc


def _positive_number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        return None
    try:
        number = float(Fraction(value)) if isinstance(value, str) else float(value)
    except (ValueError, ZeroDivisionError):
        return None
    if not isfinite(number) or number <= 0:
        return None
    return int(number) if number.is_integer() else number


def _json_safe_mapping(value: dict[Any, Any]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, bool | int | float | str) or item is None:
            result[str(key)] = item
    return result
