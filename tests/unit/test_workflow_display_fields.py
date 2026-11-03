from __future__ import annotations

from comfy_gallery_core.workflow.display_fields import widget_candidates

API_PROMPT = {
    "847": {
        "class_type": "XantaPromptLibrary",
        "inputs": {"library": "portraits"},
    },
    "827": {
        "class_type": "ShowText|pysssss",
        "inputs": {"text": ["847", 1], "text_0": "nsfw-explicit-00650"},
    },
}
BINDINGS = {"prompt_id": "827"}


def test_nested_visual_widget_value_wins_over_the_api_cache() -> None:
    visual = {
        "nodes": [
            {
                "id": 827,
                "type": "ShowText|pysssss",
                "widgets_values": [["sfw-zimage-por-v3-03786"]],
            }
        ]
    }

    candidate = widget_candidates(API_PROMPT, BINDINGS, visual)["prompt_id"]

    assert candidate == ("sfw-zimage-por-v3-03786", "visual_workflow")


def test_deeply_nested_visual_widget_values_are_walked_in_order() -> None:
    visual = {
        "nodes": [
            {
                "id": 827,
                "type": "ShowText|pysssss",
                "widgets_values": [[[]], [["first-value"], ["second-value"]]],
            }
        ]
    }

    candidate = widget_candidates(API_PROMPT, BINDINGS, visual)["prompt_id"]

    assert candidate == ("first-value", "visual_workflow")


def test_visual_widget_values_without_a_string_fall_back_to_the_api_cache() -> None:
    visual = {
        "nodes": [
            {
                "id": 827,
                "type": "ShowText|pysssss",
                "widgets_values": [[123], [], {"value": "not-a-widget-string"}],
            }
        ]
    }

    candidate = widget_candidates(API_PROMPT, BINDINGS, visual)["prompt_id"]

    assert candidate == ("nsfw-explicit-00650", "api_prompt")
