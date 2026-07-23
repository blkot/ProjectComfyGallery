from collections import namedtuple
from pathlib import Path

import pytest
from PIL import Image

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import (
    check_free_space,
    ensure_storage_layout,
    generate_derivatives,
    hash_file,
    probe_media,
    sniff_media,
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        allowed_source_roots=str(tmp_path / "imports"),
        minimum_free_bytes=0,
    )


def test_image_signature_probe_hash_and_thumbnail(tmp_path: Path) -> None:
    source = tmp_path / "misleading-name.bin"
    Image.new("RGB", (640, 320), (31, 88, 145)).save(source, format="PNG")
    settings = _settings(tmp_path)
    ensure_storage_layout(settings)

    signature = sniff_media(source)
    digest, byte_size = hash_file(source, chunk_bytes=64 * 1024)
    probe = probe_media(source, settings)
    derivatives = generate_derivatives(
        media_id="018f-test-media",
        source=source,
        probe=probe,
        settings=settings,
    )

    assert signature.kind == "image"
    assert signature.detected_format == "png"
    assert len(digest) == 64
    assert byte_size == source.stat().st_size
    assert (probe.width, probe.height) == (640, 320)
    assert len(derivatives) == 1
    assert derivatives[0].kind == "thumbnail"
    assert derivatives[0].path.is_file()
    assert derivatives[0].width == 640
    assert derivatives[0].height == 320


def test_unknown_bytes_are_rejected_by_content(tmp_path: Path) -> None:
    source = tmp_path / "looks-like-an-image.png"
    source.write_bytes(b"not really a png")

    with pytest.raises(IngestionError) as raised:
        sniff_media(source)

    assert raised.value.code == "MEDIA_UNSUPPORTED_FORMAT"


def test_low_disk_reserve_rejects_new_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    settings.minimum_free_bytes = 500
    ensure_storage_layout(settings)
    disk_usage = namedtuple("disk_usage", "total used free")
    monkeypatch.setattr(
        "comfy_gallery_core.media.files.shutil.disk_usage",
        lambda _path: disk_usage(1000, 900, 100),
    )

    with pytest.raises(IngestionError) as raised:
        check_free_space(settings, required_bytes=50)

    assert raised.value.code == "STORAGE_LOW_SPACE"
    assert raised.value.retryable is True
