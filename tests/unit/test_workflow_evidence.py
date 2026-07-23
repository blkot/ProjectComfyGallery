import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from comfy_gallery_core.config import Settings
from comfy_gallery_core.workflow.evidence import read_embedded_workflow
from comfy_gallery_core.workflow.graph import normalize_workflow_graph


def _settings() -> Settings:
    return Settings(
        environment="test",
        workflow_metadata_max_bytes=4 * 1024 * 1024,
    )


def _write_comfy_png(
    path: Path,
    *,
    prompt_text: str | None,
    workflow_text: str | None,
) -> None:
    metadata = PngImagePlugin.PngInfo()
    if prompt_text is not None:
        metadata.add_text("prompt", prompt_text)
    if workflow_text is not None:
        metadata.add_text("workflow", workflow_text)
    Image.new("RGB", (64, 48), (20, 30, 40)).save(
        path,
        format="PNG",
        pnginfo=metadata,
    )


def test_png_reader_preserves_exact_payloads_and_normalizes_unknown_nodes(
    tmp_path: Path,
) -> None:
    prompt = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "base-model.safetensors"},
        },
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "local-series_000003500.safetensors",
            },
        },
        "3": {
            "class_type": "UnknownCustomNode",
            "inputs": {"opaque": {"nested": True}},
        },
    }
    workflow = {
        "nodes": [
            {"id": 1, "type": "UNETLoader", "widgets_values": ["base-model.safetensors"]},
            {
                "id": 2,
                "type": "LoraLoaderModelOnly",
                "widgets_values": ["local-series_000003500.safetensors", 1.0],
            },
            {"id": 3, "type": "UnknownCustomNode", "widgets_values": [{"nested": True}]},
        ],
        "links": [[10, 1, 0, 2, 0, "MODEL"]],
    }
    prompt_text = json.dumps(prompt, ensure_ascii=False, indent=2)
    workflow_text = json.dumps(workflow, ensure_ascii=False, separators=(",", ":"))
    path = tmp_path / "workflow.png"
    _write_comfy_png(
        path,
        prompt_text=prompt_text,
        workflow_text=workflow_text,
    )

    evidence = read_embedded_workflow(path, _settings())
    graph = normalize_workflow_graph(evidence.api_prompt, evidence.visual_workflow)

    assert evidence.parse_status == "parsed"
    assert evidence.raw_api_prompt_text == prompt_text
    assert evidence.raw_visual_workflow_text == workflow_text
    assert graph.api_node_count == 3
    assert graph.visual_node_count == 3
    assert {node.class_type for node in graph.nodes} >= {
        "UNETLoader",
        "LoraLoaderModelOnly",
        "UnknownCustomNode",
    }
    assert {item.observation_type for item in graph.observations} == {
        "checkpoint_reference",
        "lora_reference",
    }


def test_one_malformed_representation_retains_the_other(tmp_path: Path) -> None:
    path = tmp_path / "partial.png"
    workflow_text = json.dumps({"nodes": [], "links": []})
    _write_comfy_png(
        path,
        prompt_text='{"broken":',
        workflow_text=workflow_text,
    )

    evidence = read_embedded_workflow(path, _settings())

    assert evidence.parse_status == "partial"
    assert evidence.api_prompt_status == "malformed"
    assert evidence.visual_workflow_status == "parsed"
    assert evidence.raw_api_prompt_text == '{"broken":'
    assert evidence.visual_workflow == {"nodes": [], "links": []}
    assert evidence.issues[0].code == "WORKFLOW_JSON_MALFORMED"


def test_image_without_workflow_is_a_valid_absent_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "plain.png"
    _write_comfy_png(path, prompt_text=None, workflow_text=None)

    evidence = read_embedded_workflow(path, _settings())

    assert evidence.parse_status == "absent"
    assert evidence.api_prompt is None
    assert evidence.visual_workflow is None
    assert evidence.issues == ()


@pytest.mark.parametrize(("image_format", "suffix"), [("JPEG", ".jpg"), ("WEBP", ".webp")])
def test_exif_user_comment_wrapper_supports_jpeg_and_webp(
    tmp_path: Path,
    image_format: str,
    suffix: str,
) -> None:
    prompt = {"1": {"class_type": "UnknownNode", "inputs": {"value": 4}}}
    workflow = {"nodes": [{"id": 1, "type": "UnknownNode"}], "links": []}
    wrapper = json.dumps({"prompt": json.dumps(prompt), "workflow": workflow})
    exif = Image.Exif()
    exif[37510] = b"ASCII\x00\x00\x00" + wrapper.encode()
    path = tmp_path / f"metadata{suffix}"
    Image.new("RGB", (40, 30), (50, 60, 70)).save(
        path,
        format=image_format,
        exif=exif,
    )

    evidence = read_embedded_workflow(path, _settings())

    assert evidence.parse_status == "parsed"
    assert evidence.api_prompt == prompt
    assert evidence.visual_workflow == workflow


def test_webm_comment_wrapper_uses_the_video_metadata_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "workflow.webm"
    path.write_bytes(b"\x1aE\xdf\xa3synthetic")
    prompt = {"1": {"class_type": "UnknownVideoNode", "inputs": {}}}
    workflow = {"nodes": [{"id": 1, "type": "UnknownVideoNode"}], "links": []}
    ffprobe_payload = json.dumps(
        {
            "format": {
                "tags": {
                    "COMMENT": json.dumps(
                        {
                            "prompt": json.dumps(prompt),
                            "workflow": workflow,
                        }
                    )
                }
            }
        }
    )

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 0, stdout=ffprobe_payload, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    evidence = read_embedded_workflow(path, _settings())

    assert evidence.source_carrier == "video_format_tags"
    assert evidence.parse_status == "parsed"
    assert evidence.api_prompt == prompt
    assert evidence.visual_workflow == workflow
