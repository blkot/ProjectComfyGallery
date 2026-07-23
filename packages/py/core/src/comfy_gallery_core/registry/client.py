from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlsplit, urlunsplit

import httpx

from comfy_gallery_core.config import Settings
from comfy_gallery_core.media.errors import IngestionError

USER_AGENT = "ProjectComfyGallery/0.1 registry-sync"
SUPPORTED_MODEL_FOLDERS = ("checkpoints", "diffusion_models", "unet", "loras")


def normalize_comfyui_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise IngestionError(
            code="COMFYUI_URL_INVALID",
            message="The ComfyUI URL must be an absolute HTTP or HTTPS URL.",
        )
    if parts.username or parts.password or parts.query or parts.fragment:
        raise IngestionError(
            code="COMFYUI_URL_INVALID",
            message="The ComfyUI URL cannot contain credentials, a query, or a fragment.",
        )
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = normalize_comfyui_url(base_url)
        self._maximum_bytes = settings.registry_max_response_bytes
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(settings.registry_http_timeout_seconds),
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            transport=transport,
        )

    async def __aenter__(self) -> ComfyUIClient:
        return self

    async def __aexit__(self, *_args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def system_stats(self) -> dict[str, object]:
        return _object(await self._request_json("GET", "/system_stats"), "/system_stats")

    async def features(self) -> dict[str, object]:
        return _object(await self._request_json("GET", "/features"), "/features")

    async def object_info(self) -> dict[str, object]:
        return _object(await self._request_json("GET", "/object_info"), "/object_info")

    async def model_folders(self) -> list[str]:
        payload = await self._request_json("GET", "/models")
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise _contract_error("/models", "an array of folder names")
        return cast(list[str], payload)

    async def models_in_folder(self, folder: str) -> list[str]:
        payload = await self._request_json("GET", f"/models/{folder}")
        if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
            raise _contract_error(f"/models/{folder}", "an array of model paths")
        return cast(list[str], payload)

    async def lora_manager_list(self, kind: str) -> list[dict[str, object]]:
        _validate_lora_manager_kind(kind)
        items: list[dict[str, object]] = []
        page = 1
        total_pages = 1
        while page <= total_pages:
            path = f"/api/lm/{kind}/list"
            payload = _object(
                await self._request_json(
                    "GET",
                    path,
                    params={"page": page, "page_size": 100},
                ),
                path,
            )
            raw_items = payload.get("items")
            if not isinstance(raw_items, list):
                raise _contract_error(path, "an object containing an items array")
            for raw_item in raw_items:
                if isinstance(raw_item, dict):
                    items.append({str(key): value for key, value in raw_item.items()})
            raw_total_pages = payload.get("total_pages", 1)
            total_pages = raw_total_pages if isinstance(raw_total_pages, int) else 1
            if total_pages > 10_000:
                raise _contract_error(path, "a bounded page count")
            page += 1
        return items

    async def lora_manager_scan(self, kind: str) -> dict[str, object]:
        _validate_lora_manager_kind(kind)
        path = f"/api/lm/{kind}/scan"
        return _object(await self._request_json("GET", path), path)

    async def lora_manager_fetch_all(self, kind: str) -> dict[str, object]:
        _validate_lora_manager_kind(kind)
        path = f"/api/lm/{kind}/fetch-all-civitai"
        return _object(await self._request_json("POST", path, json_body={}), path)

    async def lora_manager_metadata(
        self,
        kind: str,
        file_path: str,
    ) -> dict[str, object]:
        _validate_lora_manager_kind(kind)
        path = f"/api/lm/{kind}/metadata"
        return _object(
            await self._request_json(
                "GET",
                path,
                params={"file_path": file_path},
            ),
            path,
        )

    async def current_model_lists(self) -> dict[str, list[str]]:
        available = set(await self.model_folders())
        result: dict[str, list[str]] = {}
        for folder in SUPPORTED_MODEL_FOLDERS:
            if folder in available:
                result[folder] = await self.models_in_folder(folder)
        return result

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int | float | bool | None] | None = None,
        json_body: object | None = None,
    ) -> object:
        try:
            response = await self._client.request(
                method,
                path,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise IngestionError(
                code="COMFYUI_TIMEOUT",
                message=f"ComfyUI did not finish {path} within the configured timeout.",
                retryable=True,
                details={"path": path},
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise IngestionError(
                code="COMFYUI_HTTP_ERROR",
                message=f"ComfyUI returned HTTP {exc.response.status_code} for {path}.",
                retryable=exc.response.status_code >= 500,
                details={"path": path, "status_code": exc.response.status_code},
            ) from exc
        except httpx.HTTPError as exc:
            raise IngestionError(
                code="COMFYUI_UNAVAILABLE",
                message="ComfyUI could not be reached.",
                retryable=True,
                details={"path": path, "reason": type(exc).__name__},
            ) from exc

        if len(response.content) > self._maximum_bytes:
            raise IngestionError(
                code="COMFYUI_RESPONSE_TOO_LARGE",
                message=f"ComfyUI response {path} exceeds the configured size limit.",
                details={
                    "path": path,
                    "response_bytes": len(response.content),
                    "maximum_bytes": self._maximum_bytes,
                },
            )
        try:
            return cast(Any, response.json())
        except ValueError as exc:
            raise IngestionError(
                code="COMFYUI_RESPONSE_INVALID",
                message=f"ComfyUI response {path} is not valid JSON.",
                details={"path": path},
            ) from exc


def _object(payload: object, path: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise _contract_error(path, "a JSON object")
    return {str(key): value for key, value in payload.items()}


def _contract_error(path: str, expected: str) -> IngestionError:
    return IngestionError(
        code="COMFYUI_CONTRACT_INVALID",
        message=f"ComfyUI response {path} does not contain {expected}.",
        details={"path": path, "expected": expected},
    )


def _validate_lora_manager_kind(kind: str) -> None:
    if kind not in {"loras", "checkpoints"}:
        raise ValueError(f"Unsupported LoRA Manager inventory kind: {kind}")
