import json
from pathlib import Path

from comfy_gallery_api.main import app


def test_committed_openapi_snapshot_matches_application_contract() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    snapshot_path = repository_root / "doc" / "interfaces" / "openapi.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    current = app.openapi()

    assert snapshot == current
    assert "/api/v1/media/{media_id}/variant-imports" in current["paths"]
    assert "/api/v1/media/{media_id}/variants/{variant_id}/content" in current["paths"]
    assert "/api/v1/media/{media_id}/playback-preference" in current["paths"]
