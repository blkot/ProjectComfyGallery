from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError

THUMBNAIL_RECIPE = "image-webp-v1"
POSTER_RECIPE = "video-poster-v1"
PROXY_RECIPE = "video-h264-v1"


@dataclass(frozen=True, slots=True)
class MediaSignature:
    kind: str
    detected_format: str
    mime_type: str
    normalized_extension: str


@dataclass(frozen=True, slots=True)
class ProbeResult:
    signature: MediaSignature
    width: int | None
    height: int | None
    duration_seconds: float | None = None
    frame_rate: float | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    raw: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class GeneratedDerivative:
    kind: str
    recipe_version: str
    path: Path
    mime_type: str
    byte_size: int
    width: int | None = None
    height: int | None = None
    container: str | None = None
    codec: str | None = None


def ensure_storage_layout(settings: Settings) -> None:
    for path in (
        settings.resolved_managed_root / "originals",
        settings.resolved_managed_root / "variants",
        settings.resolved_managed_root / "derivatives",
        settings.resolved_staging_root,
        settings.resolved_export_root,
        settings.resolved_runtime_root,
    ):
        path.mkdir(parents=True, exist_ok=True)


def safe_managed_path(settings: Settings, relative_path: str) -> Path:
    root = settings.resolved_managed_root
    candidate = (root / relative_path).resolve()
    if not candidate.is_relative_to(root):
        raise IngestionError(
            code="MANAGED_PATH_INVALID",
            message="The managed file path is outside the configured storage root.",
        )
    return candidate


def check_free_space(settings: Settings, *, required_bytes: int) -> None:
    free = shutil.disk_usage(settings.resolved_managed_root).free
    required = required_bytes + settings.minimum_free_bytes
    if free < required:
        raise IngestionError(
            code="STORAGE_LOW_SPACE",
            message="There is not enough free space to preserve this media file.",
            retryable=True,
            details={"required_bytes": required, "free_bytes": free},
        )


def hash_file(path: Path, *, chunk_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_size = 0
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(chunk_bytes), b""):
                digest.update(chunk)
                byte_size += len(chunk)
    except OSError as exc:
        raise IngestionError(
            code="MEDIA_READ_FAILED",
            message="The media file could not be read.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc
    if byte_size == 0:
        raise IngestionError(
            code="MEDIA_EMPTY",
            message="Empty files cannot be imported.",
        )
    return digest.hexdigest(), byte_size


def copy_and_hash(
    source: Path,
    destination: Path,
    *,
    chunk_bytes: int,
    maximum_bytes: int | None = None,
) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    byte_size = 0
    try:
        with source.open("rb") as source_handle, destination.open("xb") as destination_handle:
            for chunk in iter(lambda: source_handle.read(chunk_bytes), b""):
                byte_size += len(chunk)
                if maximum_bytes is not None and byte_size > maximum_bytes:
                    raise IngestionError(
                        code="UPLOAD_TOO_LARGE",
                        message="The uploaded file exceeds the configured size limit.",
                    )
                digest.update(chunk)
                destination_handle.write(chunk)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
    except IngestionError:
        destination.unlink(missing_ok=True)
        raise
    except FileExistsError as exc:
        raise IngestionError(
            code="STAGING_COLLISION",
            message="A staging path collision prevented the import.",
            retryable=True,
        ) from exc
    except OSError as exc:
        destination.unlink(missing_ok=True)
        raise IngestionError(
            code="MEDIA_COPY_FAILED",
            message="The media file could not be copied into staging.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc
    if byte_size == 0:
        destination.unlink(missing_ok=True)
        raise IngestionError(code="MEDIA_EMPTY", message="Empty files cannot be imported.")
    return digest.hexdigest(), byte_size


def sniff_media(path: Path) -> MediaSignature:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
    except OSError as exc:
        raise IngestionError(
            code="MEDIA_READ_FAILED",
            message="The media header could not be read.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc

    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return MediaSignature("image", "png", "image/png", "png")
    if header.startswith(b"\xff\xd8\xff"):
        return MediaSignature("image", "jpeg", "image/jpeg", "jpg")
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return MediaSignature("image", "webp", "image/webp", "webp")
    if len(header) >= 12 and header[4:8] == b"ftyp":
        if header[8:12] == b"qt  ":
            return MediaSignature("video", "mp4", "video/quicktime", "mov")
        return MediaSignature("video", "mp4", "video/mp4", "mp4")
    if header.startswith(b"\x1aE\xdf\xa3"):
        return MediaSignature("video", "webm", "video/webm", "webm")
    raise IngestionError(
        code="MEDIA_UNSUPPORTED_FORMAT",
        message="Only PNG, JPEG, WebP, MP4, and WebM files are supported.",
    )


def probe_media(path: Path, settings: Settings) -> ProbeResult:
    signature = sniff_media(path)
    if signature.kind == "image":
        return _probe_image(path, signature)
    return _probe_video(path, signature, settings)


def _probe_image(path: Path, signature: MediaSignature) -> ProbeResult:
    try:
        with Image.open(path) as image:
            detected = (image.format or "").casefold()
            expected = "jpeg" if signature.detected_format == "jpeg" else signature.detected_format
            if detected.casefold() != expected:
                raise IngestionError(
                    code="MEDIA_TYPE_MISMATCH",
                    message="The file content does not match its detected image type.",
                )
            image.verify()
        with Image.open(path) as image:
            oriented = ImageOps.exif_transpose(image)
            width, height = oriented.size
            raw: dict[str, object] = {
                "format": detected,
                "mode": oriented.mode,
                "width": width,
                "height": height,
            }
    except IngestionError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise IngestionError(
            code="IMAGE_PROBE_FAILED",
            message="The image is corrupt or cannot be decoded.",
            details={"reason": str(exc)},
        ) from exc
    return ProbeResult(
        signature=signature,
        width=width,
        height=height,
        raw=raw,
    )


def _probe_video(path: Path, signature: MediaSignature, settings: Settings) -> ProbeResult:
    command = [
        settings.ffprobe_path,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
    ) as exc:
        raise IngestionError(
            code="VIDEO_PROBE_FAILED",
            message="The video container could not be inspected.",
            details={"reason": str(exc)},
        ) from exc

    streams = payload.get("streams", [])
    if not isinstance(streams, list):
        streams = []
    video_stream = _first_stream(streams, "video")
    audio_stream = _first_stream(streams, "audio")
    if video_stream is None:
        raise IngestionError(
            code="VIDEO_STREAM_MISSING",
            message="The video container has no video stream.",
        )
    format_payload = payload.get("format", {})
    if not isinstance(format_payload, dict):
        format_payload = {}
    container = str(format_payload.get("format_name") or signature.detected_format)
    duration = _optional_float(format_payload.get("duration"))
    frame_rate = _parse_fraction(video_stream.get("avg_frame_rate"))
    return ProbeResult(
        signature=signature,
        width=_optional_int(video_stream.get("width")),
        height=_optional_int(video_stream.get("height")),
        duration_seconds=duration,
        frame_rate=frame_rate,
        container=container,
        video_codec=_optional_string(video_stream.get("codec_name")),
        audio_codec=(
            _optional_string(audio_stream.get("codec_name")) if audio_stream is not None else None
        ),
        raw=_json_object(payload),
    )


def generate_derivatives(
    *,
    media_id: str,
    source: Path,
    probe: ProbeResult,
    settings: Settings,
) -> list[GeneratedDerivative]:
    derivative_root = settings.resolved_managed_root / "derivatives" / media_id / "v1"
    derivative_root.mkdir(parents=True, exist_ok=True)
    if probe.signature.kind == "image":
        return [_generate_thumbnail(source, derivative_root, settings)]

    generated = [_generate_poster(source, derivative_root, probe, settings)]
    if not is_browser_compatible(probe):
        generated.append(_generate_video_proxy(source, derivative_root, settings))
    return generated


def is_browser_compatible(probe: ProbeResult) -> bool:
    video_codec = (probe.video_codec or "").casefold()
    audio_codec = (probe.audio_codec or "").casefold()
    if probe.signature.detected_format == "mp4":
        return video_codec in {"h264", "av1"} and audio_codec in {"", "aac", "mp3"}
    if probe.signature.detected_format == "webm":
        return video_codec in {"vp8", "vp9", "av1"} and audio_codec in {
            "",
            "opus",
            "vorbis",
        }
    return False


def place_original(
    *,
    staged_path: Path,
    sha256: str,
    signature: MediaSignature,
    settings: Settings,
) -> tuple[Path, str]:
    destination, relative = original_location(
        sha256=sha256,
        signature=signature,
        settings=settings,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing_sha, _ = hash_file(destination, chunk_bytes=settings.hash_chunk_bytes)
        if existing_sha != sha256:
            raise IngestionError(
                code="ORIGINAL_COLLISION",
                message="Managed storage contains different bytes at the target hash path.",
            )
        staged_path.unlink(missing_ok=True)
        return destination, relative.as_posix()
    try:
        os.replace(staged_path, destination)
    except OSError as exc:
        raise IngestionError(
            code="ORIGINAL_PLACEMENT_FAILED",
            message="The immutable original could not be placed in managed storage.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc
    return destination, relative.as_posix()


def original_location(
    *,
    sha256: str,
    signature: MediaSignature,
    settings: Settings,
) -> tuple[Path, Path]:
    relative = Path("originals") / sha256[:2] / f"{sha256}.{signature.normalized_extension}"
    return settings.resolved_managed_root / relative, relative


def variant_location(
    *,
    media_id: str,
    role: str,
    sha256: str,
    signature: MediaSignature,
    settings: Settings,
) -> tuple[Path, Path]:
    relative = Path("variants") / media_id / role / f"{sha256}.{signature.normalized_extension}"
    return settings.resolved_managed_root / relative, relative


def place_variant(
    *,
    staged_path: Path,
    media_id: str,
    role: str,
    sha256: str,
    signature: MediaSignature,
    settings: Settings,
) -> tuple[Path, str]:
    destination, relative = variant_location(
        media_id=media_id,
        role=role,
        sha256=sha256,
        signature=signature,
        settings=settings,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing_sha, _ = hash_file(destination, chunk_bytes=settings.hash_chunk_bytes)
        if existing_sha != sha256:
            raise IngestionError(
                code="VARIANT_STORAGE_FAILED",
                message="Managed storage contains different bytes at the variant hash path.",
            )
        staged_path.unlink(missing_ok=True)
        return destination, relative.as_posix()
    try:
        os.replace(staged_path, destination)
    except OSError as exc:
        raise IngestionError(
            code="VARIANT_STORAGE_FAILED",
            message="The validated variant could not be placed in managed storage.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc
    return destination, relative.as_posix()


def _generate_thumbnail(
    source: Path,
    root: Path,
    settings: Settings,
) -> GeneratedDerivative:
    destination = root / "thumbnail.webp"
    temporary = root / "thumbnail.tmp.webp"
    try:
        with Image.open(source) as image:
            oriented = ImageOps.exif_transpose(image)
            oriented.thumbnail(
                (settings.thumbnail_max_dimension, settings.thumbnail_max_dimension),
                Image.Resampling.LANCZOS,
            )
            if oriented.mode not in {"RGB", "RGBA"}:
                oriented = oriented.convert("RGBA" if "A" in oriented.getbands() else "RGB")
            oriented.save(temporary, format="WEBP", quality=84, method=5)
            width, height = oriented.size
        os.replace(temporary, destination)
    except (OSError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise IngestionError(
            code="THUMBNAIL_FAILED",
            message="The image thumbnail could not be generated.",
            retryable=True,
            details={"reason": str(exc)},
        ) from exc
    return GeneratedDerivative(
        kind="thumbnail",
        recipe_version=THUMBNAIL_RECIPE,
        path=destination,
        mime_type="image/webp",
        byte_size=destination.stat().st_size,
        width=width,
        height=height,
    )


def _generate_poster(
    source: Path,
    root: Path,
    probe: ProbeResult,
    settings: Settings,
) -> GeneratedDerivative:
    destination = root / "poster.jpg"
    temporary = root / "poster.tmp.jpg"
    seek = max((probe.duration_seconds or 0) * 0.1, 0)
    command = [
        settings.ffmpeg_path,
        "-y",
        "-ss",
        f"{seek:.3f}",
        "-i",
        str(source),
        "-frames:v",
        "1",
        "-vf",
        f"scale={settings.thumbnail_max_dimension}:-2:force_original_aspect_ratio=decrease",
        "-q:v",
        "3",
        str(temporary),
    ]
    _run_ffmpeg(command, timeout=120, code="POSTER_FAILED", message="Video poster failed.")
    os.replace(temporary, destination)
    width, height = _image_dimensions(destination)
    return GeneratedDerivative(
        kind="poster",
        recipe_version=POSTER_RECIPE,
        path=destination,
        mime_type="image/jpeg",
        byte_size=destination.stat().st_size,
        width=width,
        height=height,
    )


def _generate_video_proxy(
    source: Path,
    root: Path,
    settings: Settings,
) -> GeneratedDerivative:
    destination = root / "proxy.mp4"
    temporary = root / "proxy.tmp.mp4"
    command = [
        settings.ffmpeg_path,
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    _run_ffmpeg(
        command,
        timeout=6 * 60 * 60,
        code="VIDEO_PROXY_FAILED",
        message="The browser-compatible video proxy could not be generated.",
    )
    os.replace(temporary, destination)
    return GeneratedDerivative(
        kind="video_proxy",
        recipe_version=PROXY_RECIPE,
        path=destination,
        mime_type="video/mp4",
        byte_size=destination.stat().st_size,
        container="mp4",
        codec="h264",
    )


def _run_ffmpeg(
    command: list[str],
    *,
    timeout: int,
    code: str,
    message: str,
) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        output = ""
        if isinstance(exc, subprocess.CalledProcessError):
            output = exc.stderr.decode("utf-8", errors="replace")[-2000:]
        Path(command[-1]).unlink(missing_ok=True)
        raise IngestionError(
            code=code,
            message=message,
            retryable=True,
            details={"reason": str(exc), "ffmpeg": output},
        ) from exc


def _first_stream(
    streams: list[object],
    codec_type: str,
) -> dict[str, Any] | None:
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def _optional_float(value: object) -> float | None:
    if not isinstance(value, str | int | float):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if not isinstance(value, str | int | float):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    return str(value) if value not in {None, ""} else None


def _parse_fraction(value: object) -> float | None:
    if not isinstance(value, str) or "/" not in value:
        return _optional_float(value)
    numerator, denominator = value.split("/", 1)
    try:
        divisor = float(denominator)
        return float(numerator) / divisor if divisor else None
    except ValueError:
        return None


def _json_object(payload: object) -> dict[str, object]:
    serialized = json.loads(json.dumps(payload))
    return serialized if isinstance(serialized, dict) else {}


def _image_dimensions(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def original_extension(filename: str) -> str | None:
    suffix = Path(filename).suffix.casefold().lstrip(".")
    return suffix[:32] if suffix else None


def copy_stream_to_file(
    source: BinaryIO,
    destination: Path,
    *,
    chunk_bytes: int,
    maximum_bytes: int,
) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    byte_size = 0
    with destination.open("xb") as handle:
        for chunk in iter(lambda: source.read(chunk_bytes), b""):
            byte_size += len(chunk)
            if byte_size > maximum_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise IngestionError(
                    code="UPLOAD_TOO_LARGE",
                    message="The uploaded file exceeds the configured size limit.",
                )
            handle.write(chunk)
        handle.flush()
        os.fsync(handle.fileno())
    return byte_size
