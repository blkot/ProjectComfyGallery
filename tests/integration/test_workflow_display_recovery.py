import copy
import hashlib
import json
import zipfile
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from comfy_gallery_core.workflow.display_fields import DISPLAY_KEY, saved_fields
from comfy_gallery_core.workflow.display_recovery import Target, verified_values


def test_save_node_overrides_are_per_field_and_per_output() -> None:
    graph = {
        "2": {"class_type": "Source", "inputs": {}},
        "3": {
            "class_type": "XantaSaveAndUpload",
            "inputs": {"cg_prompt_id": ["2", 1], "cg_lora_list": ["2", 0], "cg_prompt": ["2", 0]},
        },
    }
    packet = {
        "version": 1,
        "save_node_id": "3",
        "fields": {
            "prompt_id": "0007",
            "prompt": "",
            "lora_list": [],
            "character_lora": "not wired",
        },
    }

    def parse():
        return saved_fields({"text_chunks": {DISPLAY_KEY: json.dumps(packet)}}, graph)

    assert {k: v.value for k, v in parse().items()} == {
        "prompt_id": "0007",
        "prompt": "",
        "lora_list": [],
    }
    packet["save_node_id"] = "2"
    assert parse() == {}


def test_history_profile_rejects_node_collisions_stale_widgets_and_wrong_output(
    tmp_path: Path,
) -> None:
    workflow = str(uuid4())
    job_id = uuid4()
    original = b"actual original file"
    api = {
        "847": {"class_type": "XantaPromptLibrary", "inputs": {"library": "portraits", "seed": 13}},
        "827": {"class_type": "ShowText|pysssss", "inputs": {"text": ["847", 1], "text_0": "old"}},
        "837": {
            "class_type": "RegexExtract",
            "inputs": {"string": ["847", 0], "regex_pattern": "A", "group_index": 1},
        },
        "835": {"class_type": "ShowText|pysssss", "inputs": {"text": ["837", 0]}},
        "839": {"class_type": "XantaSaveAndUpload", "inputs": {}},
    }
    reference = Target(
        uuid4(), "output.png", hashlib.sha256(original).hexdigest(), len(original), api, workflow
    )
    target = replace(reference, media_id=uuid4())
    path = tmp_path / "private.zip"
    loc = {"type": "output", "filename": target.filename, "subfolder": ""}
    outputs = {"827": {"text": ["007"]}, "835": {"text": ["character"]}, "839": {"images": [loc]}}

    def archive(data):
        entry = {
            "status": {"status_str": "success"},
            "prompt": [1, str(job_id), api, {"extra_pnginfo": {"workflow": {"id": workflow}}}],
            "outputs": outputs,
        }
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("history.json", json.dumps({str(job_id): entry}))
            z.writestr("locator.json", json.dumps(loc))
            z.writestr("output.png", data)

    def verify(candidate):
        return verified_values(
            path,
            reference=reference,
            target=candidate,
            job_id=job_id,
            bindings={"prompt_id": "827", "character_lora": "835"},
        )[1]

    archive(original)
    assert verify(target) == {"prompt_id": "007", "character_lora": "character"}
    # Identical numeric IDs alone never authorize reuse.
    with pytest.raises(ValueError, match="workflow UUID"):
        verify(replace(target, workflow_id=str(uuid4())))
    different = copy.deepcopy(api)
    different["827"]["inputs"]["text"] = ["847", 0]
    with pytest.raises(ValueError, match="wiring"):
        verify(replace(target, api=different))
    different = copy.deepcopy(api)
    different["837"]["inputs"]["regex_pattern"] = "B"
    with pytest.raises(ValueError, match="regex"):
        verify(replace(target, api=different))
    archive(b"x" * len(original))
    with pytest.raises(ValueError, match="SHA-256"):
        verify(target)
    outputs["835"]["text"] = []
    archive(original)
    with pytest.raises(ValueError, match="executed text"):
        verify(target)


async def test_workflow_detail_prefers_current_output_over_verified_overlay() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from comfy_gallery_api.routes.workflows import get_media_workflow
    from comfy_gallery_core.db import Base
    from comfy_gallery_core.db.models import (
        Media,
        MediaAsset,
        WorkflowDisplayRecovery,
        WorkflowSnapshot,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            mid, job = uuid4(), uuid4()
            session.add(Media(id=mid, kind="image", status="ready"))
            await session.flush()
            session.add(
                MediaAsset(
                    media_id=mid,
                    sha256="a" * 64,
                    byte_size=1,
                    original_filename="a.png",
                    managed_path="a.png",
                )
            )
            snapshot = WorkflowSnapshot(
                media_id=mid,
                reader_name="test",
                reader_version="1",
                source_carrier="png",
                evidence_sha256="f" * 64,
                api_prompt_status="parsed",
                visual_workflow_status="absent",
                parse_status="parsed",
                api_prompt={
                    "9": {"class_type": "XantaSaveAndUpload", "inputs": {"cg_prompt_id": ["1", 1]}},
                    "1": {"class_type": "XantaPromptLibrary", "inputs": {}},
                },
                raw_metadata={
                    "text_chunks": {
                        DISPLAY_KEY: json.dumps(
                            {"version": 1, "save_node_id": "9", "fields": {"prompt_id": "new-id"}}
                        )
                    }
                },
            )
            session.add(snapshot)
            for name, value, node in (
                ("prompt_id", "old-id", "827"),
                ("character_lora", "character", "835"),
            ):
                session.add(
                    WorkflowDisplayRecovery(
                        media_id=mid,
                        field_name=name,
                        value=value,
                        original_sha256="a" * 64,
                        profile_sha256="b" * 64,
                        node_id=node,
                        job_id=job,
                    )
                )
            await session.commit()
            detail = await get_media_workflow(
                mid, None, session, representation=None, node_limit=10, node_offset=0, edge_limit=10
            )
            assert detail.display_fields["prompt_id"].value == "new-id"
            assert detail.display_fields["prompt_id"].source == "save_node"
            assert detail.display_fields["character_lora"].source == "verified_history"
            assert detail.display_fields["character_lora"].job_id == str(job)
            assert not detail.model_usages and not detail.observations
    finally:
        await engine.dispose()


async def test_offline_profile_projects_only_approved_graphs_without_job_history() -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from comfy_gallery_core.db import Base
    from comfy_gallery_core.db.models import Media, WorkflowSnapshot
    from comfy_gallery_core.workflow.display_fields import topology
    from comfy_gallery_core.workflow.library_profiles import candidate_fields, install_profile

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            uid = str(uuid4())
            nodes = {
                "847": {"class_type": "XantaPromptLibrary", "inputs": {"library": "A"}},
                "827": {
                    "class_type": "ShowText|pysssss",
                    "inputs": {"text": ["847", 1], "text_0": "cached-007"},
                },
            }
            rows = []
            for n in range(4):
                media = Media(id=uuid4(), kind="image", status="ready")
                session.add(media)
                api = copy.deepcopy(nodes)
                if n == 2:
                    api["827"]["inputs"]["text"] = ["847", 0]
                s = WorkflowSnapshot(
                    media_id=media.id,
                    reader_name="test",
                    reader_version="1",
                    source_carrier="png",
                    evidence_sha256="f" * 64,
                    api_prompt_status="parsed",
                    visual_workflow_status="parsed",
                    parse_status="parsed",
                    api_prompt=api,
                    visual_workflow={"id": uid if n != 3 else str(uuid4())},
                )
                session.add(s)
                rows.append(s)
            await session.commit()
            spec = {
                "version": 1,
                "reference_media": str(rows[0].media_id),
                "workflow_uuid": uid,
                "topology_sha256": topology(nodes),
                "bindings": {"prompt_id": "827"},
            }
            summary = await install_profile(session, spec, apply=False)
            assert summary["examined"] == 3 and summary["matched"] == 2
            assert not await candidate_fields(session, rows[0])
            for _ in range(2):
                await install_profile(session, spec, apply=True)
            assert await candidate_fields(session, rows[1]) == {"prompt_id": ("cached-007", "827")}
            assert not await candidate_fields(session, rows[2])
            assert not await candidate_fields(session, rows[3])
            with pytest.raises(ValueError, match="different mapping"):
                await install_profile(
                    session, {**spec, "bindings": {"character_lora": "827"}}, apply=True
                )
    finally:
        await engine.dispose()
