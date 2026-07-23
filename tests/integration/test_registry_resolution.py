from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    ExtractionRun,
    LoraSeries,
    LoraSeriesMember,
    Media,
    ModelArtifact,
    ModelReference,
    ModelUsage,
    SemanticObservation,
    WorkflowEdge,
    WorkflowNode,
    WorkflowSnapshot,
)
from comfy_gallery_core.registry.models import (
    _resolve_lora_series,
    import_model_inventory,
    merge_lora_series,
    resolve_model_references,
    split_lora_series,
)
from comfy_gallery_core.registry.nodes import resolve_workflow_nodes


async def test_historical_nodes_model_links_pipeline_slots_and_lora_series() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(kind="video", status="ready")
        session.add(media)
        await session.flush()
        snapshot = WorkflowSnapshot(
            media_id=media.id,
            reader_name="test",
            reader_version="1",
            source_carrier="test",
            evidence_sha256="e" * 64,
            raw_metadata={},
            api_prompt={},
            visual_workflow=None,
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
            graph_version="generic-graph-v1",
        )
        session.add(snapshot)
        await session.flush()
        high_loader = _node(snapshot.id, 0, "1", "UnetLoaderGGUF", {"unet_name": "high.gguf"})
        low_loader = _node(snapshot.id, 1, "2", "UnetLoaderGGUF", {"unet_name": "low.gguf"})
        high_sampler = _node(
            snapshot.id,
            2,
            "3",
            "KSamplerAdvanced",
            {"model": ["1", 0], "steps": 6, "latent_image": ["9", 0]},
        )
        low_sampler = _node(
            snapshot.id,
            3,
            "4",
            "KSamplerAdvanced",
            {"model": ["2", 0], "steps": 6, "latent_image": ["3", 0]},
        )
        lora_node = _node(
            snapshot.id,
            4,
            "5",
            "LoraLoaderModelOnly",
            {"lora_name": "Krea2_guzong_lora_v2_000003500.safetensors"},
        )
        session.add_all([high_loader, low_loader, high_sampler, low_sampler, lora_node])
        await session.flush()
        session.add_all(
            [
                _edge(snapshot.id, 0, "1", "3", "model"),
                _edge(snapshot.id, 1, "3", "4", "latent_image"),
                _edge(snapshot.id, 2, "2", "4", "model"),
            ]
        )
        run = ExtractionRun(
            snapshot_id=snapshot.id,
            extractor_name="test",
            extractor_version="1",
            graph_version="generic-graph-v1",
            configuration_hash="c" * 64,
            reason="test",
            status="succeeded",
            is_current=True,
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                _observation(run.id, high_loader.id, "checkpoint_reference", "high.gguf"),
                _observation(run.id, low_loader.id, "checkpoint_reference", "low.gguf"),
                _observation(
                    run.id,
                    lora_node.id,
                    "lora_reference",
                    "Krea2_guzong_lora_v2_000003500.safetensors",
                ),
                ModelArtifact(
                    artifact_type="gguf",
                    display_name="High",
                    file_name="high.gguf",
                    file_path="high.gguf",
                    provider="test",
                    identity_state="registry_known",
                    availability="present",
                    enrichment_state="matched",
                    architecture_family="Wan Video 2.2 I2V-A14B",
                ),
                ModelArtifact(
                    artifact_type="gguf",
                    display_name="Low",
                    file_name="low.gguf",
                    file_path="low.gguf",
                    provider="test",
                    identity_state="registry_known",
                    availability="present",
                    enrichment_state="matched",
                    architecture_family="Wan Video 2.2 I2V-A14B",
                ),
            ]
        )
        await session.commit()

        node_outcome = await resolve_workflow_nodes(session)
        model_outcome = await resolve_model_references(session)

        assert node_outcome.historical_count == 3
        assert node_outcome.matched_count == 5
        assert model_outcome.resolved_count == 2
        assert model_outcome.historical_count == 1
        usages = list(
            await session.scalars(
                select(ModelUsage).order_by(ModelUsage.observation_type, ModelUsage.slot)
            )
        )
        checkpoint_usages = [
            usage for usage in usages if usage.observation_type == "checkpoint_reference"
        ]
        assert {(usage.pipeline_pattern, usage.slot) for usage in checkpoint_usages} == {
            ("dual_noise", "high_noise"),
            ("dual_noise", "low_noise"),
        }
        series = await session.scalar(select(LoraSeries))
        member = await session.scalar(select(LoraSeriesMember))
        assert series is not None
        assert member is not None
        assert series.opaque_name == "Krea2_guzong_lora_v2"
        assert member.training_step == 3500
        historical = await session.scalar(
            select(ModelReference).where(ModelReference.resolution_state == "historical")
        )
        assert historical is not None
        assert historical.availability == "missing"

    await engine.dispose()


async def test_import_model_inventory_accepts_new_artifacts_before_defaults_flush() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        outcome = await import_model_inventory(
            session,
            lora_items=[
                {
                    "model_name": "Personal Adapter",
                    "file_name": "Krea2_personal_000003500.safetensors",
                    "file_path": "loras/Krea2_personal_000003500.safetensors",
                    "sha256": "a" * 64,
                }
            ],
            checkpoint_items=[],
            folder_models={
                "loras": ["Krea2/Krea2_personal_000003500.safetensors"],
            },
            metadata_by_path={},
            enrichment_attempted=True,
        )
        artifact = await session.scalar(select(ModelArtifact))

        assert outcome.artifact_count == 1
        assert outcome.fallback_count == 0
        assert artifact is not None
        assert artifact.display_name == "Personal Adapter"
        assert artifact.availability == "present"

    await engine.dispose()


async def test_inventory_infers_wan_architecture_and_krea_lineage_from_strong_names() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        await import_model_inventory(
            session,
            lora_items=[],
            checkpoint_items=[
                {
                    "model_name": "wan2.2_i2v_high_noise_14B_Q4_K_S",
                    "file_name": "wan2.2_i2v_high_noise_14B_Q4_K_S.gguf",
                    "file_path": "wan/wan2.2_i2v_high_noise_14B_Q4_K_S.gguf",
                },
                {
                    "model_name": "Krea 2 Turbo INT8",
                    "file_name": "krea2TurboINT8.safetensors",
                    "file_path": "Krea2/krea2TurboINT8.safetensors",
                },
            ],
            folder_models={},
            metadata_by_path={},
            enrichment_attempted=False,
        )
        artifacts = list(
            await session.scalars(select(ModelArtifact).order_by(ModelArtifact.display_name))
        )

        assert {(artifact.architecture_family, artifact.lineage) for artifact in artifacts} == {
            ("Wan 2.2", None),
            ("Krea 2", "Turbo"),
        }

    await engine.dispose()


async def test_manual_lora_series_merge_and_split_survive_automatic_resolution() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        references = [
            ModelReference(
                reference_type="lora",
                raw_value="Character_A_000001000.safetensors",
                normalized_value="Character_A_000001000.safetensors",
                availability="unknown",
                resolution_state="historical",
                occurrence_count=1,
            ),
            ModelReference(
                reference_type="lora",
                raw_value="Character_A_000002000.safetensors",
                normalized_value="Character_A_000002000.safetensors",
                availability="unknown",
                resolution_state="historical",
                occurrence_count=1,
            ),
            ModelReference(
                reference_type="lora",
                raw_value="Different_name_000003000.safetensors",
                normalized_value="Different_name_000003000.safetensors",
                availability="unknown",
                resolution_state="historical",
                occurrence_count=1,
            ),
        ]
        session.add_all(references)
        await session.flush()
        await _resolve_lora_series(session, references)
        await session.commit()

        series_records = list(await session.scalars(select(LoraSeries)))
        by_name = {series.opaque_name: series for series in series_records}
        await merge_lora_series(
            session,
            target=by_name["Character_A"],
            sources=[by_name["Different_name"]],
        )

        character_members = list(
            await session.scalars(
                select(LoraSeriesMember).where(
                    LoraSeriesMember.series_id == by_name["Character_A"].id
                )
            )
        )
        member_to_split = next(
            member for member in character_members if member.model_reference_id == references[1].id
        )
        custom = await split_lora_series(
            session,
            source=by_name["Character_A"],
            member_ids=[member_to_split.id],
            opaque_name="My_manual_training_run",
            display_name="My manual training run",
        )

        await _resolve_lora_series(session, references)
        await session.commit()
        final_series = list(await session.scalars(select(LoraSeries)))
        final_members = list(await session.scalars(select(LoraSeriesMember)))

        assert {series.opaque_name for series in final_series} == {
            "Character_A",
            "My_manual_training_run",
        }
        assert len(final_members) == 3
        assignments = {member.model_reference_id: member.series_id for member in final_members}
        assert assignments[references[1].id] == custom.id
        assert assignments[references[2].id] == by_name["Character_A"].id

    await engine.dispose()


def _node(
    snapshot_id: object,
    ordinal: int,
    node_id: str,
    class_type: str,
    inputs: dict[str, object],
) -> WorkflowNode:
    return WorkflowNode(
        snapshot_id=snapshot_id,
        representation="api_prompt",
        ordinal=ordinal,
        original_node_id=node_id,
        class_type=class_type,
        raw_properties={},
        raw_widgets=[],
        raw_inputs=inputs,
    )


def _edge(
    snapshot_id: object,
    ordinal: int,
    source: str,
    destination: str,
    input_name: str,
) -> WorkflowEdge:
    return WorkflowEdge(
        snapshot_id=snapshot_id,
        representation="api_prompt",
        ordinal=ordinal,
        source_node_id=source,
        destination_node_id=destination,
        destination_input_name=input_name,
        raw_link=[source, destination],
    )


def _observation(
    run_id: object,
    node_id: object,
    observation_type: str,
    value: str,
) -> SemanticObservation:
    return SemanticObservation(
        run_id=run_id,
        node_id=node_id,
        observation_type=observation_type,
        role="unclassified",
        value=value,
        confidence=0.99,
        evidence={},
    )
