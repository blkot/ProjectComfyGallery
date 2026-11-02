import importlib.util
import json
import shutil
from pathlib import Path

from PIL import Image, PngImagePlugin
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from uuid6 import uuid7

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    ExtractionRun,
    Job,
    Media,
    ModelReference,
    ModelUsage,
    SemanticObservation,
    WorkflowNode,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.files import ensure_storage_layout
from comfy_gallery_core.media.ingestion import ingest_staged_file
from comfy_gallery_core.media.jobs import begin_job
from comfy_gallery_core.workflow.extraction import extract_workflow_for_media


def _settings(tmp_path: Path) -> Settings:
    import_root = tmp_path / "imports"
    import_root.mkdir()
    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        allowed_source_roots=str(import_root),
        minimum_free_bytes=0,
        thumbnail_max_dimension=128,
    )
    ensure_storage_layout(settings)
    return settings


def _make_workflow_image(
    path: Path,
    *,
    malformed_prompt: bool = False,
    non_finite_prompt: bool = False,
) -> None:
    prompt: dict[str, object] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": "checkpoint.safetensors"},
        },
        "2": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "character_000003500.safetensors",
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "plain prompt text"},
        },
    }
    if non_finite_prompt:
        prompt["4"] = {
            "class_type": "CustomNode",
            "inputs": {},
            "is_changed": float("nan"),
        }
    workflow = {
        "nodes": [
            {"id": 1, "type": "UNETLoader", "widgets_values": ["checkpoint.safetensors"]},
            {
                "id": 2,
                "type": "LoraLoaderModelOnly",
                "widgets_values": ["character_000003500.safetensors"],
            },
            {"id": 3, "type": "CLIPTextEncode", "widgets_values": ["plain prompt text"]},
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
    }
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("prompt", "{" if malformed_prompt else json.dumps(prompt))
    metadata.add_text("workflow", json.dumps(workflow))
    Image.new("RGB", (96, 64), (90, 40, 120)).save(
        path,
        format="PNG",
        pnginfo=metadata,
    )


async def test_ingestion_persists_immutable_evidence_graph_and_versioned_runs(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "workflow.png"
    staged = settings.resolved_staging_root / "workflow.upload"
    _make_workflow_image(source)
    shutil.copy2(source, staged)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        job = Job(
            kind="test_ingest",
            queue="test",
            resource_type="test",
            resource_id=uuid7(),
            progress_total=1,
        )
        session.add(job)
        await session.commit()
        assert await begin_job(session, job)
        outcome = await ingest_staged_file(
            session,
            staged_path=staged,
            original_filename=source.name,
            job=job,
            settings=settings,
        )

        snapshot = await session.scalar(
            select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == outcome.media_id)
        )
        assert snapshot is not None
        evidence_hash = snapshot.evidence_sha256
        assert snapshot.parse_status == "parsed"
        assert snapshot.api_node_count == 3
        assert snapshot.visual_node_count == 3
        assert await session.scalar(select(func.count()).select_from(WorkflowNode)) == 6
        assert await session.scalar(select(func.count()).select_from(SemanticObservation)) == 3
        correction_states = set(await session.scalars(select(SemanticObservation.correction_state)))
        assert correction_states == {"uncorrected"}

        second = await extract_workflow_for_media(
            session,
            media_id=outcome.media_id,
            settings=settings,
            reason="test_reprocess",
        )
        await session.refresh(snapshot)
        assert second.snapshot_id == snapshot.id
        assert snapshot.evidence_sha256 == evidence_hash
        assert await session.scalar(select(func.count()).select_from(ExtractionRun)) == 2
        current_runs = await session.scalar(
            select(func.count())
            .select_from(ExtractionRun)
            .where(ExtractionRun.is_current.is_(True))
        )
        assert current_runs == 1
        assert await session.scalar(select(func.count()).select_from(SemanticObservation)) == 6

    await engine.dispose()


async def test_malformed_prompt_is_non_blocking_and_preserved(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "partial.png"
    staged = settings.resolved_staging_root / "partial.upload"
    _make_workflow_image(source, malformed_prompt=True)
    shutil.copy2(source, staged)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        job = Job(
            kind="test_partial",
            queue="test",
            resource_type="test",
            resource_id=uuid7(),
            progress_total=1,
        )
        session.add(job)
        await session.commit()
        assert await begin_job(session, job)
        outcome = await ingest_staged_file(
            session,
            staged_path=staged,
            original_filename=source.name,
            job=job,
            settings=settings,
        )

        media = await session.get(Media, outcome.media_id)
        snapshot = await session.scalar(
            select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == outcome.media_id)
        )
        assert media is not None
        assert snapshot is not None
        assert media.status == "ready_with_warnings"
        assert snapshot.parse_status == "partial"
        assert snapshot.raw_api_prompt_text == "{"
        assert snapshot.api_prompt is None
        assert snapshot.visual_workflow is not None

    await engine.dispose()


async def test_non_finite_workflow_values_do_not_block_ingestion(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "non-finite.png"
    staged = settings.resolved_staging_root / "non-finite.upload"
    _make_workflow_image(source, non_finite_prompt=True)
    shutil.copy2(source, staged)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        job = Job(
            kind="test_non_finite",
            queue="test",
            resource_type="test",
            resource_id=uuid7(),
            progress_total=1,
        )
        session.add(job)
        await session.commit()
        assert await begin_job(session, job)

        outcome = await ingest_staged_file(
            session,
            staged_path=staged,
            original_filename=source.name,
            job=job,
            settings=settings,
        )

        media = await session.get(Media, outcome.media_id)
        snapshot = await session.scalar(
            select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == outcome.media_id)
        )
        run = await session.scalar(
            select(ExtractionRun).where(ExtractionRun.snapshot_id == snapshot.id)
        )
        assert media is not None
        assert snapshot is not None
        assert run is not None
        assert media.status == "ready_with_warnings"
        assert outcome.ready_with_warnings
        assert snapshot.raw_api_prompt_text is not None
        assert '"is_changed": NaN' in snapshot.raw_api_prompt_text
        assert snapshot.api_prompt is not None
        assert snapshot.api_prompt["4"]["is_changed"] is None
        assert snapshot.issue_details["issues"][0]["code"] == (
            "WORKFLOW_NON_FINITE_NUMBER_NORMALIZED"
        )
        assert run.status == "completed_with_warnings"

    await engine.dispose()


async def test_snapshot_persistence_failure_is_non_blocking(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = tmp_path / "persistence-failure.png"
    staged = settings.resolved_staging_root / "persistence-failure.upload"
    _make_workflow_image(source)
    shutil.copy2(source, staged)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    def reject_workflow_snapshot(session: Session, *_args: object) -> None:
        if any(isinstance(record, WorkflowSnapshot) for record in session.new):
            raise ValueError("synthetic JSON persistence failure")

    event.listen(Session, "before_flush", reject_workflow_snapshot)
    try:
        async with session_factory() as session:
            job = Job(
                kind="test_snapshot_failure",
                queue="test",
                resource_type="test",
                resource_id=uuid7(),
                progress_total=1,
            )
            session.add(job)
            await session.commit()
            assert await begin_job(session, job)

            outcome = await ingest_staged_file(
                session,
                staged_path=staged,
                original_filename=source.name,
                job=job,
                settings=settings,
            )

            media = await session.get(Media, outcome.media_id)
            snapshot = await session.scalar(
                select(WorkflowSnapshot).where(WorkflowSnapshot.media_id == outcome.media_id)
            )
            assert media is not None
            assert snapshot is None
            assert media.status == "ready_with_warnings"
            assert media.last_error_code == "WORKFLOW_SNAPSHOT_PERSIST_FAILED"
            assert outcome.ready_with_warnings
    finally:
        event.remove(Session, "before_flush", reject_workflow_snapshot)
        await engine.dispose()


def _execution_recorder():
    path = (
        Path(__file__).resolve().parents[2]
        / "integrations/comfyui/comfy_gallery_execution_capture/__init__.py"
    )
    spec = importlib.util.spec_from_file_location("execution_capture", path)
    assert spec and spec.loader
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    return plugin.NODE_CLASS_MAPPINGS["ComfyGalleryRecordExecution"]()


async def test_dynamic_conditioning_and_lora_stack_import_and_reprocessing(tmp_path: Path) -> None:
    """Replay a dynamic library → text merge → encoder, and a cycler + stack → loader."""
    settings = _settings(tmp_path)
    entry = {"name": "style", "active": True, "strength": 0.6, "clipStrength": 0.4}
    prompt = {
        "1": {"class_type": "XantaPromptLibrary", "inputs": {"library": "portraits"}},
        "2": {
            "class_type": "StringFunction|pysssss",
            "inputs": {"text_a": ["1", 0], "result": "previous execution"},
        },
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": ["2", 0]}},
        "4": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["3", 0]}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "positive": ["3", 0],
                "negative": ["4", 0],
                "model": ["9", 0],
            },
        },
        "6": {
            "class_type": "Lora Cycler (LoraManager)",
            "inputs": {
                "cycler_config": {"current_lora_filename": "previous", "current_index": 2},
            },
        },
        "7": {
            "class_type": "Lora Stacker (LoraManager)",
            "inputs": {
                "loras": {"__value__": [entry, {**entry, "name": "disabled", "active": False}]},
            },
        },
        "8": {
            "class_type": "Lora Stack Combiner (LoraManager)",
            "inputs": {
                "lora_stack1": ["6", 0],
                "lora_stack2": ["7", 0],
            },
        },
        "9": {
            "class_type": "Lora Loader (LoraManager)",
            "inputs": {
                "lora_stack": ["8", 0],
                "loras": [{**entry, "name": "local"}],
            },
        },
        "10": {
            "class_type": "Lora Stacker (LoraManager)",
            "inputs": {
                "loras": [{**entry, "name": "not connected"}],
            },
        },
    }
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for capture in (False, True):
                metadata = PngImagePlugin.PngInfo()
                if capture:
                    prompt["11"] = {
                        "class_type": "ComfyGalleryRecordExecution",
                        "inputs": {"positive": ["2", 0], "stack": ["6", 0]},
                    }
                    pnginfo: dict[str, object] = {}
                    recorder = _execution_recorder()
                    pixels = object()
                    assert recorder.record(
                        pixels,
                        positive="expanded this run",
                        stack=[("cycled.safetensors", 0.7, 0.5)],
                        extra_pnginfo=pnginfo,
                        unique_id="11",
                    ) == (pixels,)
                    for name, value in pnginfo.items():
                        metadata.add_text(name, json.dumps(value))
                metadata.add_text("prompt", json.dumps(prompt))
                path = settings.resolved_staging_root / "dynamic.png"
                Image.new("RGB", (16, 16)).save(path, pnginfo=metadata)
                job = Job(
                    kind="test",
                    queue="test",
                    resource_type="test",
                    resource_id=uuid7(),
                    progress_total=1,
                )
                session.add(job)
                await session.commit()
                await begin_job(session, job)
                result = await ingest_staged_file(
                    session,
                    staged_path=path,
                    original_filename="dynamic.png",
                    job=job,
                    settings=settings,
                )
                for reason in ("ingest", "reprocess"):
                    if reason == "reprocess":
                        await extract_workflow_for_media(
                            session, media_id=result.media_id, settings=settings, reason=reason
                        )
                    obs = list(
                        await session.scalars(
                            select(SemanticObservation)
                            .join(ExtractionRun)
                            .join(WorkflowSnapshot)
                            .where(
                                WorkflowSnapshot.media_id == result.media_id,
                                ExtractionRun.is_current,
                            )
                        )
                    )
                    loras = {x.value for x in obs if x.observation_type == "lora_reference"}
                    assert loras == {"local", "style"} | (
                        {"cycled.safetensors"} if capture else set()
                    )
                    indexed = set(
                        await session.scalars(
                            select(ModelReference.raw_value)
                            .join(ModelUsage, ModelUsage.model_reference_id == ModelReference.id)
                            .join(WorkflowSnapshot, WorkflowSnapshot.id == ModelUsage.snapshot_id)
                            .where(WorkflowSnapshot.media_id == result.media_id)
                        )
                    )
                    assert indexed == loras
                    assert [(x.role, x.value) for x in obs if x.observation_type == "prompt"] == (
                        [("positive", "expanded this run")] if capture else []
                    )
                    assert {
                        x.observation_type
                        for x in obs
                        if x.observation_type.endswith("_unresolved")
                    } == (set() if capture else {"prompt_unresolved", "lora_unresolved"})
    finally:
        await engine.dispose()


def test_runtime_capture_is_bound_to_the_same_wire_and_ambiguous_values_stay_unknown() -> None:
    from comfy_gallery_core.registry.dynamic_sources import dynamic_fields

    pnginfo: dict[str, dict] = {}
    recorder = _execution_recorder()
    recorder.record(None, positive="one", stack=[], extra_pnginfo=pnginfo, unique_id="tap")
    recorder.record(None, positive="two", stack=[], extra_pnginfo=pnginfo, unique_id="tap")
    assert pnginfo["comfy_gallery_execution_v1"]["tap"] == {"positive": None, "stack": []}

    source = WorkflowNode(
        id=uuid7(),
        representation="api_prompt",
        original_node_id="source",
        class_type="XantaPromptLibrary",
        raw_inputs={},
    )
    encoder = WorkflowNode(
        id=uuid7(),
        representation="api_prompt",
        original_node_id="encoder",
        class_type="CLIPTextEncode",
        raw_inputs={"text": ["source", 0]},
    )
    tap = WorkflowNode(
        id=uuid7(),
        representation="api_prompt",
        original_node_id="tap",
        class_type="ComfyGalleryRecordExecution",
        raw_inputs={"positive": ["source", 1]},
    )

    def extract(encoded: str):
        return [
            (f.semantic_type, f.value)
            for f in dynamic_fields(
                [source, encoder, tap],
                {encoder.id: "positive"},
                {"text_chunks": {"comfy_gallery_execution_v1": encoded}},
            )
        ]

    assert extract(json.dumps({"tap": {"positive": "library label from slot 1"}})) == [
        ("prompt_unresolved", "XantaPromptLibrary")
    ]
    tap.raw_inputs = {"positive": ["source", 0]}
    assert extract(json.dumps(pnginfo["comfy_gallery_execution_v1"])) == [
        ("prompt_unresolved", "XantaPromptLibrary")
    ]
    assert extract("{") == [("prompt_unresolved", "XantaPromptLibrary")]
