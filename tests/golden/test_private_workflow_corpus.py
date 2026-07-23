from hashlib import sha256
from pathlib import Path

import pytest

from comfy_gallery_core.config import Settings
from comfy_gallery_core.workflow.evidence import read_embedded_workflow
from comfy_gallery_core.workflow.graph import normalize_workflow_graph


def _golden_files() -> list[Path]:
    root = Path("testdata/golden")
    supported = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}
    organized = list(root.glob("**/original.*"))
    incoming = [
        path
        for path in root.glob("**/incoming/*")
        if path.is_file() and path.suffix.casefold() in supported
    ]
    return sorted({*organized, *incoming})


def test_private_golden_corpus_parses_without_losing_representations() -> None:
    paths = _golden_files()
    if not paths:
        pytest.skip("Private golden corpus is not present.")

    settings = Settings(environment="test")
    structural_signatures: set[str] = set()
    visual_statuses: set[str] = set()
    observation_types: set[str] = set()

    for path in paths:
        evidence = read_embedded_workflow(path, settings)
        graph = normalize_workflow_graph(evidence.api_prompt, evidence.visual_workflow)
        classes = sorted((node.representation, node.class_type) for node in graph.nodes)
        structural_signatures.add(sha256(repr(classes).encode()).hexdigest())
        visual_statuses.add(evidence.visual_workflow_status)
        observation_types.update(item.observation_type for item in graph.observations)

        assert evidence.parse_status == "parsed", path
        assert evidence.api_prompt_status == "parsed", path
        assert graph.api_node_count > 0, path
        assert len(evidence.evidence_sha256) == 64

    assert len(structural_signatures) >= 5
    assert "parsed" in visual_statuses
    assert {"checkpoint_reference", "lora_reference"} <= observation_types
