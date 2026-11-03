from __future__ import annotations

from types import SimpleNamespace

from comfy_gallery_core.workflow.prompt_index import structural_prompt_id_candidate


def _snapshot(api: dict[str, object], nodes: list[dict[str, object]]) -> SimpleNamespace:
    return SimpleNamespace(
        api_prompt=api,
        visual_workflow={"id": "6f1e9d0c-1d5e-4a55-9b4d-1a9a1f5c0e11", "nodes": nodes},
        media_id="6f1e9d0c-1d5e-4a55-9b4d-1a9a1f5c0e12",
    )


def test_structural_candidate_uses_the_library_wired_prompt_node() -> None:
    api = {
        "71": {
            "class_type": "XantaPromptLibrary",
            "inputs": {"library": "sfw-zimage-por-v2"},
        },
        "66": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 0]}},
        "72": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 2]}},
        "73": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 1]}},
    }
    nodes = [
        {"id": 66, "type": "ShowText|pysssss", "widgets_values": [["A long prompt text"]]},
        {
            "id": 72,
            "type": "ShowText|pysssss",
            "widgets_values": [["framing:closeup, style:photo"]],
        },
        {"id": 73, "type": "ShowText|pysssss", "widgets_values": [["nsfw-explicit-04094"]]},
    ]

    assert structural_prompt_id_candidate(_snapshot(api, nodes)) == "nsfw-explicit - 04094"


def test_structural_candidate_fails_closed_when_ids_are_ambiguous() -> None:
    api = {
        "71": {"class_type": "XantaPromptLibrary", "inputs": {"library": "library"}},
        "73": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 1]}},
        "74": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 2]}},
    }
    nodes = [
        {"id": 73, "type": "ShowText|pysssss", "widgets_values": ["source-a-0001"]},
        {"id": 74, "type": "ShowText|pysssss", "widgets_values": ["source-b-0002"]},
    ]

    assert structural_prompt_id_candidate(_snapshot(api, nodes)) is None


def test_structural_candidate_ignores_showtext_nodes_not_wired_to_a_library() -> None:
    api = {
        "71": {"class_type": "XantaPromptLibrary", "inputs": {"library": "library"}},
        "80": {"class_type": "CLIPTextEncode", "inputs": {"text": "plain text"}},
        "73": {"class_type": "ShowText|pysssss", "inputs": {"text": ["80", 0]}},
    }
    nodes = [
        {"id": 73, "type": "ShowText|pysssss", "widgets_values": [["source-a-0001"]]},
    ]

    assert structural_prompt_id_candidate(_snapshot(api, nodes)) is None


def test_structural_candidate_requires_a_visual_snapshot() -> None:
    api = {
        "71": {"class_type": "XantaPromptLibrary", "inputs": {"library": "library"}},
        "73": {"class_type": "ShowText|pysssss", "inputs": {"text": ["71", 1]}},
    }
    snapshot = SimpleNamespace(
        api_prompt=api,
        visual_workflow=None,
        media_id="6f1e9d0c-1d5e-4a55-9b4d-1a9a1f5c0e12",
    )

    assert structural_prompt_id_candidate(snapshot) is None
