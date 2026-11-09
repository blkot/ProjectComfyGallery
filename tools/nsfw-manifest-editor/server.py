#!/usr/bin/env python3
"""Serve the local manifest editor and safely write into this WSL checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = Path(__file__).resolve().parents[2]
EDITOR_FILE = Path(__file__).with_name("index.html")
SAMPLES_DIR = REPO_ROOT / "testdata" / "nsfw" / "samples"
MANIFEST_FILE = REPO_ROOT / "testdata" / "nsfw" / "manifest.local.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MAX_IMAGE_BYTES = 64 * 1024 * 1024
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
RATINGS = {"safe", "sexy", "nudity", "explicit", "review"}


class RequestError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def safe_sample_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (
        not normalized
        or normalized.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise RequestError(400, "图片路径必须是 samples 文件夹内的相对路径。")

    relative = PurePosixPath(normalized)
    if relative.suffix.lower() not in IMAGE_EXTENSIONS:
        raise RequestError(415, "只支持 JPG、PNG、WebP、BMP 和 TIFF 图片。")

    root = SAMPLES_DIR.resolve()
    target = (root / Path(*relative.parts)).resolve()
    if not target.is_relative_to(root):
        raise RequestError(400, "图片路径不能离开 samples 文件夹。")
    return target


def list_sample_files() -> list[str]:
    root = SAMPLES_DIR.resolve()
    files: list[str] = []
    for path in SAMPLES_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        resolved = path.resolve()
        if resolved.is_relative_to(root):
            files.append(path.relative_to(SAMPLES_DIR).as_posix())
    return sorted(files, key=str.casefold)


def validate_manifest(payload: object, *, require_images: bool) -> dict[str, list[dict[str, str]]]:
    if not isinstance(payload, dict) or not isinstance(payload.get("images"), list):
        raise RequestError(400, "清单格式不正确：需要包含 images 数组。")
    entries = payload["images"]
    if require_images and not entries:
        raise RequestError(400, "清单至少需要包含一张图片。")
    if len(entries) > 10_000:
        raise RequestError(413, "单份清单最多支持 10,000 张图片。")

    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for index, raw in enumerate(entries, start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("file"), str):
            raise RequestError(400, f"第 {index} 条记录缺少 file 文件名。")
        relative = raw["file"].replace("\\", "/")
        sample_path = safe_sample_path(relative)
        if relative in seen:
            raise RequestError(400, f"清单包含重复图片：{relative}")
        seen.add(relative)
        if require_images and not sample_path.is_file():
            raise RequestError(400, f"samples 中找不到图片：{relative}")

        rating = raw.get("expected_rating")
        if rating is not None and (not isinstance(rating, str) or rating not in RATINGS):
            raise RequestError(
                400, f"{relative} 的标签必须是 safe、sexy、nudity、explicit 或 review。"
            )
        notes = raw.get("notes", "")
        if not isinstance(notes, str):
            raise RequestError(400, f"{relative} 的 notes 必须是文字。")

        entry = {"file": relative}
        if rating is not None:
            entry["expected_rating"] = rating
        if notes.strip():
            entry["notes"] = notes.strip()
        normalized.append(entry)
    return {"images": normalized}


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


class ManifestEditorHandler(BaseHTTPRequestHandler):
    server_version = "LocalManifestEditor/1.0"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    @property
    def allowed_origins(self) -> set[str]:
        port = self.server.server_port
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}

    def _check_local_request(self) -> None:
        expected_hosts = {
            f"127.0.0.1:{self.server.server_port}",
            f"localhost:{self.server.server_port}",
        }
        if self.headers.get("Host", "") not in expected_hosts:
            raise RequestError(403, "该工具只接受 localhost 请求。")
        origin = self.headers.get("Origin")
        if origin and origin not in self.allowed_origins:
            raise RequestError(403, "跨来源请求已拒绝。")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _body(self, maximum: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError as exc:
            raise RequestError(400, "Content-Length 无效。") from exc
        if length < 0:
            raise RequestError(411, "请求需要 Content-Length。")
        if length > maximum:
            raise RequestError(413, f"请求体过大，限制为 {maximum // (1024 * 1024)} MiB。")
        body = self.rfile.read(length)
        if len(body) != length:
            raise RequestError(400, "请求体未完整传输。")
        return body

    def do_GET(self) -> None:
        try:
            self._check_local_request()
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            if parsed.path in {"/", "/index.html"}:
                self._send_bytes(200, EDITOR_FILE.read_bytes(), "text/html; charset=utf-8")
                return
            if parsed.path == "/api/state":
                manifest: dict[str, list[dict[str, str]]] = {"images": []}
                if MANIFEST_FILE.is_file():
                    try:
                        manifest = validate_manifest(
                            json.loads(MANIFEST_FILE.read_text(encoding="utf-8")),
                            require_images=False,
                        )
                    except (OSError, json.JSONDecodeError, RequestError) as exc:
                        message = exc.message if isinstance(exc, RequestError) else str(exc)
                        raise RequestError(
                            500, f"无法读取现有 manifest.local.json：{message}"
                        ) from exc
                self._send_json(200, {"manifest": manifest, "samples": list_sample_files()})
                return
            if parsed.path == "/api/sample":
                value = query.get("path", [""])[0]
                path = safe_sample_path(value)
                if not path.is_file():
                    raise RequestError(404, "samples 中找不到这张图片。")
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                self._send_bytes(200, path.read_bytes(), content_type)
                return
            raise RequestError(404, "找不到请求的资源。")
        except RequestError as exc:
            self._send_json(exc.status, {"error": exc.message})
        except (OSError, BrokenPipeError) as exc:
            self._send_json(500, {"error": f"本地读取失败：{exc}"})

    def do_POST(self) -> None:
        try:
            self._check_local_request()
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            if parsed.path == "/api/upload":
                relative = query.get("path", [""])[0]
                path = safe_sample_path(relative)
                content = self._body(MAX_IMAGE_BYTES)
                SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
                path.parent.mkdir(parents=True, exist_ok=True)

                if path.exists():
                    existing_hash = hashlib.sha256(path.read_bytes()).digest()
                    incoming_hash = hashlib.sha256(content).digest()
                    if existing_hash != incoming_hash:
                        raise RequestError(
                            409, f"WSL 中已存在不同内容的同名文件：{relative}。请先重命名。"
                        )
                    self._send_json(200, {"file": relative, "status": "already_exists"})
                    return

                atomic_write(path, content)
                self._send_json(201, {"file": relative, "status": "uploaded"})
                return

            if parsed.path == "/api/manifest":
                body = self._body(MAX_MANIFEST_BYTES)
                try:
                    payload = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise RequestError(400, "清单不是有效的 UTF-8 JSON。") from exc
                manifest = validate_manifest(payload, require_images=True)
                atomic_write(
                    MANIFEST_FILE,
                    (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
                )
                self._send_json(200, {"saved": True, "path": str(MANIFEST_FILE)})
                return

            raise RequestError(404, "找不到请求的资源。")
        except RequestError as exc:
            self._send_json(exc.status, {"error": exc.message})
        except (OSError, BrokenPipeError) as exc:
            self._send_json(500, {"error": f"本地写入失败：{exc}"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), ManifestEditorHandler)
    print(f"NSFW 清单编辑器： http://127.0.0.1:{args.port}")
    print(f"WSL 项目： {REPO_ROOT}")
    print("仅监听本机；按 Ctrl-C 停止。", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
