from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dramatiq import Broker, Worker
from dramatiq.middleware import Middleware

from comfy_gallery_core.config import Settings

WORKER_HEARTBEAT_FILENAME = "worker-heartbeat.json"


def write_worker_heartbeat(path: Path, *, state: str, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    payload = {
        "state": state,
        "version": version,
        "pid": os.getpid(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_worker_heartbeat(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


class WorkerHeartbeatMiddleware(Middleware):
    def __init__(self, *, settings: Settings, version: str) -> None:
        self.path = settings.resolved_runtime_root / WORKER_HEARTBEAT_FILENAME
        self.interval_seconds = settings.worker_heartbeat_interval_seconds
        self.version = version
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def after_worker_boot(self, broker: Broker, worker: Worker) -> None:
        del broker, worker
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            name="worker-heartbeat",
            daemon=True,
        )
        self._thread.start()

    def before_worker_shutdown(self, broker: Broker, worker: Worker) -> None:
        del broker, worker
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        write_worker_heartbeat(self.path, state="stopped", version=self.version)

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            write_worker_heartbeat(self.path, state="running", version=self.version)
            self._stop_event.wait(self.interval_seconds)
