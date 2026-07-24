from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    ExtractionRun,
    Media,
    ModelReference,
    ModelUsage,
    NodeDefinition,
    NodeSemanticMapping,
    SemanticObservation,
    WorkflowNode,
    WorkflowSnapshot,
    WorkflowValue,
)
from comfy_gallery_core.registry.models import resolve_model_references
from comfy_gallery_core.registry.nodes import create_registry_observations


async def test_structured_lora_mapping_emits_only_active_adapter_references() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        media = Media(kind="image", status="ready")
        session.add(media)
        await session.flush()
        snapshot = WorkflowSnapshot(
            media_id=media.id,
            reader_name="test",
            reader_version="1",
            source_carrier="test",
            evidence_sha256="e" * 64,
            raw_metadata={},
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
        )
        definition = NodeDefinition(
            class_type="Lora加载器(Lora管理器)",
            python_module="",
            schema_fingerprint="4e4f028a9510bc0a096d0c6747ad41d043cbde9690cec791a7a884f5d25a3216",
            source_kind="workflow",
            input_schema={},
            output_schema=[],
            raw_definition={},
            mapping_state="manual",
        )
        session.add_all([snapshot, definition])
        await session.flush()
        mapping = NodeSemanticMapping(
            node_definition_id=definition.id,
            locator="input:loras",
            input_name="loras",
            semantic_type="lora_reference",
            role="adapter",
            source="manual",
            confidence=1,
            state="active",
            correction_state="corrected",
            evidence={},
        )
        node = WorkflowNode(
            snapshot_id=snapshot.id,
            node_definition_id=definition.id,
            representation="api_prompt",
            ordinal=0,
            original_node_id="1",
            class_type="Lora加载器(Lora管理器)",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        session.add_all([mapping, node])
        await session.flush()
        session.add(
            WorkflowValue(
                node_id=node.id,
                locator="input:loras",
                input_name="loras",
                value_kind="object",
                raw_value={
                    "**value**": [
                        _lora("Krea2_guzong_lora_v2_000006750", active=True, strength="1.00"),
                        _lora("realism_engine_krea2_v3.1", active=False, strength=1),
                        _lora("RealisticSnapshotKrea2", active=True, strength="0.65"),
                        _lora("Krea2_HMNSFW_AIO", active=False, strength=1),
                        _lora("Krea2_wls_lora_v1_000007000", active=False, strength=1),
                        _lora("wls_boob_krea_lora_v1_000003000", active=True, strength=1),
                    ]
                },
                normalized_text=None,
            )
        )
        run = ExtractionRun(
            snapshot_id=snapshot.id,
            extractor_name="test",
            extractor_version="1",
            graph_version="generic-graph-v1",
            configuration_hash="f" * 64,
            reason="test",
            status="running",
            is_current=True,
        )
        session.add(run)
        await session.commit()

        outcome = await create_registry_observations(
            session,
            run_id=run.id,
            snapshot_id=snapshot.id,
        )
        run.status = "succeeded"
        await session.commit()
        resolved = await resolve_model_references(session, snapshot_ids={snapshot.id})

        observations = list(
            await session.scalars(
                select(SemanticObservation).where(
                    SemanticObservation.run_id == run.id,
                    SemanticObservation.observation_type == "lora_reference",
                )
            )
        )
        assert outcome.created_count == 3
        assert {observation.value for observation in observations} == {
            "Krea2_guzong_lora_v2_000006750",
            "RealisticSnapshotKrea2",
            "wls_boob_krea_lora_v1_000003000",
        }
        realistic = next(
            observation
            for observation in observations
            if observation.value == "RealisticSnapshotKrea2"
        )
        assert realistic.evidence["value_method"] == "active_lora_collection"
        assert realistic.evidence["collection_container"] == "**value**"
        assert realistic.evidence["strength"] == "0.65"
        assert resolved.reference_count == 3
        assert resolved.usage_count == 3
        assert len(list(await session.scalars(select(ModelReference)))) == 3
        assert len(list(await session.scalars(select(ModelUsage)))) == 3

    await engine.dispose()


def _lora(name: str, *, active: bool, strength: str | int) -> dict[str, object]:
    return {
        "name": name,
        "active": active,
        "locked": False,
        "expanded": False,
        "strength": strength,
        "clipStrength": strength,
    }
