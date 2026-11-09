from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from starlette.concurrency import run_in_threadpool

IDLE_TIMEOUT_SECONDS = max(30, int(os.getenv("NSFW_IDLE_TIMEOUT_SECONDS", "480")))
MAX_IMAGE_BYTES = max(1024, int(os.getenv("NSFW_MAX_IMAGE_BYTES", str(64 * 1024 * 1024))))
WORKER_HOST = "127.0.0.1"
WORKER_PORT = 8002
WORKER_URL = f"http://{WORKER_HOST}:{WORKER_PORT}"
WORKER_SCRIPT = Path(__file__).with_name("inference_worker.py")

_worker_lock = threading.Lock()
_worker: subprocess.Popen[bytes] | None = None
_last_request_at = 0.0
_stop_reaper = threading.Event()
_reaper: threading.Thread | None = None


def _stop_worker() -> None:
    global _worker
    process = _worker
    _worker = None
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _worker_is_ready() -> bool:
    try:
        response = httpx.get(f"{WORKER_URL}/health", timeout=1.0)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def _ensure_worker() -> None:
    global _worker
    if _worker is not None and _worker.poll() is None and _worker_is_ready():
        return
    _stop_worker()
    child_env = os.environ.copy()
    child_env.setdefault("HF_HUB_OFFLINE", "1")
    child_env.setdefault("TRANSFORMERS_OFFLINE", "1")
    child_env.setdefault("OMP_NUM_THREADS", "2")
    child_env.setdefault("MKL_NUM_THREADS", "2")
    _worker = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "inference_worker:app",
            "--host",
            WORKER_HOST,
            "--port",
            str(WORKER_PORT),
            "--workers",
            "1",
        ],
        cwd=WORKER_SCRIPT.parent,
        env=child_env,
        stdin=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + float(os.getenv("NSFW_MODEL_START_TIMEOUT_SECONDS", "240"))
    while time.monotonic() < deadline:
        if _worker.poll() is not None:
            raise RuntimeError("The NSFW model process exited while loading the model.")
        if _worker_is_ready():
            return
        time.sleep(0.5)
    _stop_worker()
    raise TimeoutError("The NSFW model process did not become ready before the timeout.")


def _classify_with_worker(image_bytes: bytes) -> dict[str, object]:
    global _last_request_at
    with _worker_lock:
        _ensure_worker()
        try:
            response = httpx.post(
                f"{WORKER_URL}/classify",
                content=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=float(os.getenv("NSFW_INFERENCE_TIMEOUT_SECONDS", "180")),
            )
            if response.status_code >= 400:
                detail = "The NSFW model process rejected the image."
                try:
                    response_detail = response.json().get("detail")
                    if isinstance(response_detail, str):
                        detail = response_detail[:500]
                except (ValueError, AttributeError):
                    pass
                raise HTTPException(status_code=response.status_code, detail=detail)
            payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError("The NSFW model process became unavailable.") from exc
        finally:
            _last_request_at = time.monotonic()
        return payload


def _reap_idle_worker() -> None:
    while not _stop_reaper.wait(1):
        with _worker_lock:
            if (
                _worker is not None
                and _worker.poll() is None
                and _last_request_at
                and time.monotonic() - _last_request_at >= IDLE_TIMEOUT_SECONDS
            ):
                _stop_worker()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    global _reaper
    _stop_reaper.clear()
    _reaper = threading.Thread(target=_reap_idle_worker, name="nsfw-idle-reaper", daemon=True)
    _reaper.start()
    try:
        yield
    finally:
        _stop_reaper.set()
        if _reaper is not None:
            _reaper.join(timeout=2)
        with _worker_lock:
            _stop_worker()


app = FastAPI(title="Comfy Gallery NSFW Runtime", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    process = _worker
    return {
        "status": "ok",
        "model_process_running": process is not None and process.poll() is None,
        "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
    }


@app.post("/classify")
async def classify(request: Request) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=413, detail="Image exceeds the configured size limit."
                )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from exc

    image_bytes = bytearray()
    async for chunk in request.stream():
        image_bytes.extend(chunk)
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="Image exceeds the configured size limit.")
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image body is empty.")

    try:
        return await run_in_threadpool(_classify_with_worker, bytes(image_bytes))
    except TimeoutError as exc:
        raise HTTPException(
            status_code=503, detail="The NSFW model did not start in time."
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
