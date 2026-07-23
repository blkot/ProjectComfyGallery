import json
from datetime import UTC, datetime, timedelta

from comfy_gallery_api.routes.system import _backup_check, _worker_check
from comfy_gallery_core.config import Settings
from comfy_gallery_core.operations.heartbeat import (
    WORKER_HEARTBEAT_FILENAME,
    write_worker_heartbeat,
)


def _settings(tmp_path) -> Settings:
    return Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        export_root=tmp_path / "exports",
        backup_root=tmp_path / "backups",
        runtime_root=tmp_path / "runtime",
        worker_stale_after_seconds=30,
        backup_expected_interval_hours=24,
    )


def test_worker_heartbeat_reports_running_and_stale(tmp_path) -> None:
    settings = _settings(tmp_path)
    heartbeat_path = settings.resolved_runtime_root / WORKER_HEARTBEAT_FILENAME
    write_worker_heartbeat(heartbeat_path, state="running", version="test")
    assert _worker_check(settings).status == "ok"

    stale = {
        "state": "running",
        "version": "test",
        "updated_at": (datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
    }
    heartbeat_path.write_text(json.dumps(stale), encoding="utf-8")
    assert _worker_check(settings).status == "error"


def test_backup_status_persists_failure_and_detects_overdue_backup(tmp_path) -> None:
    settings = _settings(tmp_path)
    settings.resolved_backup_root.mkdir(parents=True)
    status_path = settings.resolved_backup_root / ".backup-status.json"
    status_path.write_text(
        json.dumps({"status": "error", "attempted_at": datetime.now(UTC).isoformat()}),
        encoding="utf-8",
    )
    assert _backup_check(settings).status == "error"

    status_path.write_text(
        json.dumps(
            {
                "status": "ok",
                "backup_id": "old",
                "completed_at": (datetime.now(UTC) - timedelta(hours=48)).isoformat(),
                "byte_size": 10,
            }
        ),
        encoding="utf-8",
    )
    assert _backup_check(settings).status == "warning"
