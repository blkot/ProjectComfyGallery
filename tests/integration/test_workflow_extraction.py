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
