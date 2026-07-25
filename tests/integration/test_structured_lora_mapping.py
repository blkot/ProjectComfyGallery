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
    WorkflowEdge,
    WorkflowNode,
    WorkflowSnapshot,
    WorkflowValue,
)
from comfy_gallery_core.registry.models import resolve_model_references
from comfy_gallery_core.registry.nodes import (
    _mapped_observation_values,
    create_registry_observations,
)


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
                    "__value__": [
                        _lora("Krea2_guzong_lora_v2_000006750", active=True, strength="1.00"),
                        _lora("realism_engine_krea2_v3.1", active=True, strength=1),
                        _lora("RealisticSnapshotKrea2", active=False, strength="0.65"),
                        _lora("Krea2_HMNSFW_AIO", active=False, strength=1),
                        _lora("Krea2_wls_lora_v1_000007000", active=False, strength=1),
                        _lora("wls_boob_krea_lora_v1_000003000", active=False, strength=1),
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
        assert outcome.created_count == 2
        assert {observation.value for observation in observations} == {
            "Krea2_guzong_lora_v2_000006750",
            "realism_engine_krea2_v3.1",
        }
        realism = next(
            observation
            for observation in observations
            if observation.value == "realism_engine_krea2_v3.1"
        )
        assert realism.evidence["value_method"] == "active_lora_collection"
        assert realism.evidence["collection_container"] == "__value__"
        assert realism.evidence["strength"] == 1
        assert resolved.reference_count == 2
        assert resolved.usage_count == 2
        assert len(list(await session.scalars(select(ModelReference)))) == 2
        assert len(list(await session.scalars(select(ModelUsage)))) == 2

    await engine.dispose()


async def test_prompt_mapping_infers_conditioning_roles_and_overrides_builtin_role() -> None:
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
            evidence_sha256="p" * 64,
            raw_metadata={},
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
        )
        definition = NodeDefinition(
            class_type="Text_o",
            python_module="",
            schema_fingerprint="prompt-role-test",
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
            locator="input:text",
            input_name="text",
            semantic_type="prompt",
            role=None,
            source="manual",
            confidence=1,
            state="active",
            correction_state="corrected",
            evidence={},
        )
        positive_source = WorkflowNode(
            snapshot_id=snapshot.id,
            node_definition_id=definition.id,
            representation="api_prompt",
            ordinal=0,
            original_node_id="positive-text",
            class_type="Text_o",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        positive_encoder = WorkflowNode(
            snapshot_id=snapshot.id,
            representation="api_prompt",
            ordinal=1,
            original_node_id="positive-encode",
            class_type="CLIPTextEncode",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        negative_source = WorkflowNode(
            snapshot_id=snapshot.id,
            node_definition_id=definition.id,
            representation="api_prompt",
            ordinal=2,
            original_node_id="negative-text",
            class_type="Text_o",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        negative_encoder = WorkflowNode(
            snapshot_id=snapshot.id,
            representation="api_prompt",
            ordinal=3,
            original_node_id="negative-encode",
            class_type="CLIPTextEncode",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        sampler = WorkflowNode(
            snapshot_id=snapshot.id,
            representation="api_prompt",
            ordinal=4,
            original_node_id="sampler",
            class_type="KSampler",
            raw_properties={},
            raw_widgets=[],
            raw_inputs={},
        )
        session.add_all(
            [
                mapping,
                positive_source,
                positive_encoder,
                negative_source,
                negative_encoder,
                sampler,
            ]
        )
        await session.flush()
        session.add_all(
            [
                WorkflowValue(
                    node_id=positive_source.id,
                    locator="input:text",
                    input_name="text",
                    value_kind="string",
                    raw_value="the intended scene",
                    normalized_text="the intended scene",
                ),
                WorkflowValue(
                    node_id=negative_source.id,
                    locator="input:text",
                    input_name="text",
                    value_kind="string",
                    raw_value="artifacts, blur",
                    normalized_text="artifacts, blur",
                ),
                _workflow_edge(snapshot.id, 0, "positive-text", "positive-encode", "text"),
                _workflow_edge(snapshot.id, 1, "positive-encode", "sampler", "positive"),
                _workflow_edge(snapshot.id, 2, "negative-text", "negative-encode", "text"),
                _workflow_edge(snapshot.id, 3, "negative-encode", "sampler", "negative"),
            ]
        )
        run = ExtractionRun(
            snapshot_id=snapshot.id,
            extractor_name="test",
            extractor_version="1",
            graph_version="generic-graph-v1",
            configuration_hash="r" * 64,
            reason="test",
            status="running",
            is_current=True,
        )
        session.add(run)
        await session.flush()
        session.add(
            SemanticObservation(
                run_id=run.id,
                node_id=positive_source.id,
                observation_type="prompt",
                role="unclassified",
                value="the intended scene",
                confidence=0.9,
                evidence={"input_name": "text", "method": "named_api_input"},
            )
        )
        await session.commit()

        outcome = await create_registry_observations(
            session,
            run_id=run.id,
            snapshot_id=snapshot.id,
        )
        await session.commit()

        observations = list(
            await session.scalars(
                select(SemanticObservation)
                .where(
                    SemanticObservation.run_id == run.id,
                    SemanticObservation.observation_type == "prompt",
                )
                .order_by(SemanticObservation.value)
            )
        )
        assert outcome.created_count == 1
        assert {str(observation.value): observation.role for observation in observations} == {
            "artifacts, blur": "negative",
            "the intended scene": "positive",
        }
        positive = next(
            observation for observation in observations if observation.value == "the intended scene"
        )
        assert positive.correction_state == "corrected"
        assert positive.evidence["prompt_role_method"] == "conditioning_graph"
        assert positive.evidence["mapping_source"] == "manual"

    await engine.dispose()


def _workflow_edge(
    snapshot_id: object,
    ordinal: int,
    source_node_id: str,
    destination_node_id: str,
    destination_input_name: str,
) -> WorkflowEdge:
    return WorkflowEdge(
        snapshot_id=snapshot_id,
        representation="api_prompt",
        ordinal=ordinal,
        source_node_id=source_node_id,
        destination_node_id=destination_node_id,
        destination_input_name=destination_input_name,
        raw_link=[source_node_id, destination_node_id],
    )


def test_structured_lora_mapping_keeps_literal_legacy_wrapper_compatibility() -> None:
    observations = _mapped_observation_values(
        "lora_reference",
        {"**value**": [_lora("legacy_adapter", active=True, strength=1)]},
    )

    assert [observation.value for observation in observations] == ["legacy_adapter"]
    assert observations[0].evidence["collection_container"] == "**value**"


def _lora(name: str, *, active: bool, strength: str | int) -> dict[str, object]:
    return {
        "name": name,
        "active": active,
        "locked": False,
        "expanded": False,
        "strength": strength,
        "clipStrength": strength,
    }
