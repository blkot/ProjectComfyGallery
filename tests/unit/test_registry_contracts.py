import httpx
import pytest

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.models import NodeDefinition
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.registry.client import ComfyUIClient, normalize_comfyui_url
from comfy_gallery_core.registry.models import parse_lora_training_series
from comfy_gallery_core.registry.nodes import (
    node_schema_fingerprint,
    suggest_definition_mappings,
)


async def test_comfyui_client_handles_lora_manager_pagination_and_model_folders() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/lm/loras/list":
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "items": [{"file_path": f"item-{page}.safetensors"}],
                    "total": 2,
                    "page": page,
                    "page_size": 1,
                    "total_pages": 2,
                },
            )
        if request.url.path == "/models":
            return httpx.Response(200, json=["loras", "diffusion_models"])
        if request.url.path == "/models/loras":
            return httpx.Response(200, json=["adapter.safetensors"])
        if request.url.path == "/models/diffusion_models":
            return httpx.Response(200, json=["model.gguf"])
        raise AssertionError(f"Unexpected request: {request.url}")

    settings = Settings(environment="test")
    async with ComfyUIClient(
        "http://comfy.test:8188/",
        settings,
        transport=httpx.MockTransport(handler),
    ) as client:
        items = await client.lora_manager_list("loras")
        folders = await client.current_model_lists()

    assert [item["file_path"] for item in items] == [
        "item-1.safetensors",
        "item-2.safetensors",
    ]
    assert folders == {
        "diffusion_models": ["model.gguf"],
        "loras": ["adapter.safetensors"],
    }


def test_comfyui_url_rejects_credentials_and_node_fingerprint_ignores_combo_values() -> None:
    with pytest.raises(IngestionError, match="cannot contain credentials"):
        normalize_comfyui_url("http://user:password@comfy.test:8188")

    first: dict[str, object] = {
        "python_module": "nodes",
        "input": {"required": {"unet_name": [["a.safetensors", "b.safetensors"]]}},
        "output": ["MODEL"],
    }
    second: dict[str, object] = {
        "python_module": "nodes",
        "input": {"required": {"unet_name": [["c.safetensors"]]}},
        "output": ["MODEL"],
    }
    assert node_schema_fingerprint("UNETLoader", first) == node_schema_fingerprint(
        "UNETLoader",
        second,
    )


def test_node_mapping_suggestions_and_opaque_lora_series_rule() -> None:
    definition = NodeDefinition(
        class_type="CustomLoader",
        python_module="custom.nodes",
        schema_fingerprint="a" * 64,
        source_kind="comfyui",
        input_schema={
            "required": {
                "model_name": [["model.safetensors"]],
                "lora_name": [["adapter.safetensors"]],
            }
        },
        output_schema=["MODEL"],
        raw_definition={},
    )
    suggestions = {
        suggestion.input_name: suggestion.semantic_type
        for suggestion in suggest_definition_mappings(definition)
    }
    assert suggestions == {
        "model_name": "checkpoint_reference",
        "lora_name": "lora_reference",
    }

    parsed = parse_lora_training_series("Krea2_guzong_lora_v2_000003500.safetensors")
    assert parsed is not None
    assert parsed.opaque_name == "Krea2_guzong_lora_v2"
    assert parsed.training_step == 3500
    assert parse_lora_training_series("Krea2_guzong_lora_v2.safetensors") is None
