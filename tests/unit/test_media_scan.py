from pathlib import Path

import pytest

from comfy_gallery_core.media.scan import iter_media_files


@pytest.mark.parametrize(
    "metadata_directory",
    [
        ".@__thumb",
        "@eaDir",
        ".thumbnails",
        ".AppleDouble",
        ".Spotlight-V100",
        ".Trash-1000",
        "#recycle",
        "@Recycle",
        "System Volume Information",
    ],
)
def test_source_scan_prunes_nas_metadata_directories(
    tmp_path: Path,
    metadata_directory: str,
) -> None:
    source_root = tmp_path / "imports"
    source_root.mkdir()
    original = source_root / "ComfyUI_00001_.png"
    original.write_bytes(b"original")

    metadata_root = source_root / "nested" / metadata_directory
    metadata_root.mkdir(parents=True)
    for prefix in ("default", "s100", "s800", "s2000"):
        (metadata_root / f"{prefix}ComfyUI_00001_.png").write_bytes(b"thumbnail")

    discovered = {
        path.relative_to(source_root).as_posix() for path in iter_media_files(source_root)
    }

    assert discovered == {"ComfyUI_00001_.png"}


def test_source_scan_does_not_prune_unrecognized_hidden_directories(tmp_path: Path) -> None:
    source_root = tmp_path / "imports"
    hidden_album = source_root / ".curated"
    hidden_album.mkdir(parents=True)
    media = hidden_album / "keeper.webp"
    media.write_bytes(b"media")

    assert list(iter_media_files(source_root)) == [media]
