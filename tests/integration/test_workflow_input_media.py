import asyncio
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from uuid6 import uuid7

from comfy_gallery_api.routes.workflow_inputs import (
    get_workflow_input_content,
    list_workflow_inputs,
    resolve_workflow_inputs,
)
from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    Media,
    NodeDefinition,
    NodeSemanticMapping,
    WorkflowInputAsset,
    WorkflowInputReference,
    WorkflowNode,
    WorkflowSnapshot,
    WorkflowValue,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.media.files import ensure_storage_layout
from comfy_gallery_core.workflow.input_media import (
    ComfyUIInputClient,
    create_capture_job_if_needed,
    detect_input_candidates,
    discover_workflow_inputs,
    process_workflow_input_job,
)


def _settings(tmp_path: Path) -> Settings:
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        export_root=tmp_path / "exports",
        runtime_root=tmp_path / "runtime",
        minimum_free_bytes=0,
        comfyui_base_url="http://comfy.test:8188",
        workflow_input_max_bytes=1024 * 1024,
    )
    ensure_storage_layout(settings)
    return settings


def _png_bytes(color: tuple[int, int, int] = (30, 80, 140)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 16), color).save(buffer, format="PNG")
    return buffer.getvalue()


class _AsyncBytes(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self.content = content

    async def __aiter__(self):
        yield self.content


async def _add_media_with_input(
    session,
    *,
    filename: str,
    class_type: str = "LoadImage",
    input_name: str = "image",
) -> tuple[Media, WorkflowSnapshot]:
    media = Media(kind="image", status="ready")
    snapshot = WorkflowSnapshot(
        media=media,
        reader_name="test",
        reader_version="1",
        source_carrier="png_text",
        evidence_sha256=(filename.encode().hex() + "0" * 64)[:64],
        raw_metadata={},
        api_prompt={},
        visual_workflow=None,
        api_prompt_status="parsed",
        visual_workflow_status="absent",
        parse_status="parsed",
        issue_details={},
    )
    node = WorkflowNode(
        snapshot=snapshot,
        representation="api_prompt",
        ordinal=0,
        original_node_id="17",
        class_type=class_type,
        raw_properties={},
        raw_widgets=[],
        raw_inputs={input_name: filename},
    )
    session.add_all((media, snapshot, node))
    await session.flush()
    session.add(
        WorkflowValue(
            node_id=node.id,
            locator=f"input:{input_name}",
            input_name=input_name,
            value_kind="string",
            raw_value=filename,
            normalized_text=filename,
        )
    )
    await session.commit()
    return media, snapshot


async def test_capture_is_durable_deduplicated_and_exposed_by_api(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    requested: list[dict[str, str]] = []
    content = _png_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(dict(request.url.params))
        return httpx.Response(
            200,
            stream=_AsyncBytes(content),
            headers={"Content-Type": "image/png"},
        )

    queued: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "comfy_gallery_api.routes.workflow_inputs.enqueue_workflow_input_capture",
        lambda *, media_id, job_id: queued.append((media_id, job_id)) or "message-id",
    )

    async with session_factory() as session:
        first_media, first_snapshot = await _add_media_with_input(
            session,
            filename="references/source.png",
        )
        second_media, second_snapshot = await _add_media_with_input(
            session,
            filename="references/source.png",
        )
        first_discovery = await discover_workflow_inputs(
            session,
            snapshot_id=first_snapshot.id,
            settings=settings,
        )
        second_discovery = await discover_workflow_inputs(
            session,
            snapshot_id=second_snapshot.id,
            settings=settings,
        )
        assert first_discovery.created_count == 1
        assert second_discovery.created_count == 1

        accepted = await resolve_workflow_inputs(
            media_id=first_media.id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
        )
        assert queued == [(str(first_media.id), str(accepted.job.id))]
        first_outcome = await process_workflow_input_job(
            session,
            media_id=first_media.id,
            job_id=accepted.job.id,
            settings=settings,
            transport=httpx.MockTransport(handler),
        )
        assert first_outcome is not None
        assert first_outcome.ready_count == 1

        second_reservation = await create_capture_job_if_needed(
            session,
            media_id=second_media.id,
            settings=settings,
        )
        assert second_reservation.job is not None
        second_outcome = await process_workflow_input_job(
            session,
            media_id=second_media.id,
            job_id=second_reservation.job.id,
            settings=settings,
            transport=httpx.MockTransport(handler),
        )
        assert second_outcome is not None
        assert second_outcome.ready_count == 1

        references = list(
            await session.scalars(
                select(WorkflowInputReference).order_by(WorkflowInputReference.created_at)
            )
        )
        assert len(references) == 2
        assert references[0].input_asset_id == references[1].input_asset_id
        assert await session.scalar(select(func.count()).select_from(WorkflowInputAsset)) == 1
        asset = await session.get(WorkflowInputAsset, references[0].input_asset_id)
        assert asset is not None
        stored_content = await asyncio.to_thread(
            (settings.resolved_managed_root / asset.managed_path).read_bytes
        )
        assert stored_content == content
        assert requested == [
            {"filename": "source.png", "type": "input", "subfolder": "references"},
            {"filename": "source.png", "type": "input", "subfolder": "references"},
        ]

        listed = await list_workflow_inputs(
            media_id=first_media.id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
        )
        assert listed.total == 1
        assert listed.ready_count == 1
        assert listed.items[0].asset is not None
        assert listed.items[0].asset.sha256 == asset.sha256
        assert listed.items[0].content_url is not None

        response = await get_workflow_input_content(
            media_id=first_media.id,
            input_id=references[0].id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            settings=settings,
        )
        response_content = await asyncio.to_thread(Path(response.path).read_bytes)
        assert response_content == content
        assert response.media_type == "image/png"

    await engine.dispose()


async def test_missing_comfyui_input_is_recorded_without_failing_capture_job(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media, snapshot = await _add_media_with_input(session, filename="deleted.png")
        await discover_workflow_inputs(session, snapshot_id=snapshot.id, settings=settings)
        reservation = await create_capture_job_if_needed(
            session,
            media_id=media.id,
            settings=settings,
        )
        assert reservation.job is not None
        outcome = await process_workflow_input_job(
            session,
            media_id=media.id,
            job_id=reservation.job.id,
            settings=settings,
            transport=httpx.MockTransport(lambda _request: httpx.Response(404)),
        )
        assert outcome is not None
        assert outcome.missing_count == 1
        await session.refresh(reservation.job)
        assert reservation.job.status == "succeeded"
        reference = await session.scalar(select(WorkflowInputReference))
        assert reference is not None
        assert reference.status == "missing"
        assert reference.last_error_code == "WORKFLOW_INPUT_NOT_FOUND"

    await engine.dispose()


def test_input_candidate_parses_asset_hash_and_rejects_traversal() -> None:
    node = WorkflowNode(
        id=uuid7(),
        snapshot_id=uuid7(),
        representation="api_prompt",
        ordinal=0,
        original_node_id="17",
        class_type="LoadImage",
        raw_properties={},
        raw_widgets=[],
        raw_inputs={"image": "blake3:abc123"},
    )
    node.values = [
        WorkflowValue(
            node_id=node.id,
            locator="input:image",
            input_name="image",
            value_kind="string",
            raw_value="blake3:abc123",
            normalized_text="blake3:abc123",
        )
    ]
    candidates = detect_input_candidates(node)
    assert len(candidates) == 1
    assert candidates[0].source_filename == "blake3:abc123"
    assert candidates[0].source_subfolder is None

    node.values[0].raw_value = "../private.png"
    assert detect_input_candidates(node) == ()


def test_manual_node_mapping_supports_custom_input_loader() -> None:
    definition = NodeDefinition(
        id=uuid7(),
        class_type="OpaqueMediaSource",
        python_module="custom.inputs",
        schema_fingerprint="a" * 64,
        source_kind="workflow",
        input_schema={},
        output_schema=[],
        raw_definition={},
    )
    definition.mappings = [
        NodeSemanticMapping(
            node_definition_id=definition.id,
            locator="input:asset",
            input_name="asset",
            semantic_type="input_media_reference",
            role="video",
            source="manual",
            confidence=1.0,
            state="active",
            correction_state="corrected",
            evidence={},
        )
    ]
    node = WorkflowNode(
        id=uuid7(),
        snapshot_id=uuid7(),
        node_definition=definition,
        representation="api_prompt",
        ordinal=0,
        original_node_id="custom-1",
        class_type="OpaqueMediaSource",
        raw_properties={},
        raw_widgets=[],
        raw_inputs={"asset": "clips/reference.mov"},
    )
    node.values = [
        WorkflowValue(
            node_id=node.id,
            locator="input:asset",
            input_name="asset",
            value_kind="string",
            raw_value="clips/reference.mov",
            normalized_text="clips/reference.mov",
        )
    ]

    candidates = detect_input_candidates(node)

    assert len(candidates) == 1
    assert candidates[0].media_kind_hint == "video"
    assert candidates[0].source_filename == "reference.mov"
    assert candidates[0].source_subfolder == "clips"
    assert candidates[0].discovery_method == "node_registry_mapping"


async def test_comfyui_input_client_rejects_redirects_and_declared_oversize(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.comfyui_user = "operator"
    reference = WorkflowInputReference(
        snapshot_id=uuid7(),
        representation="api_prompt",
        original_node_id="17",
        class_type="LoadImage",
        locator="input:image",
        input_name="image",
        media_kind_hint="image",
        source_filename="reference.png",
        source_type="input",
        raw_value="reference.png",
    )

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "comfy.test"
        assert request.headers["comfy-user"] == "operator"
        return httpx.Response(302, headers={"Location": "http://untrusted.test/file"})

    async with ComfyUIInputClient(
        settings.comfyui_base_url or "",
        settings,
        transport=httpx.MockTransport(redirect_handler),
    ) as client:
        with pytest.raises(IngestionError) as redirect:
            await client.download_input(reference, tmp_path / "redirect.download")
    assert redirect.value.code == "WORKFLOW_INPUT_REDIRECT_REJECTED"

    async with ComfyUIInputClient(
        settings.comfyui_base_url or "",
        settings,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"Content-Length": str(settings.workflow_input_max_bytes + 1)},
            )
        ),
    ) as client:
        with pytest.raises(IngestionError) as oversized:
            await client.download_input(reference, tmp_path / "oversized.download")
    assert oversized.value.code == "WORKFLOW_INPUT_TOO_LARGE"
