from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.analytics.service import _load_model_uses
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    Media,
    ModelArtifact,
    ModelReference,
    ModelUsage,
    WorkflowSnapshot,
)
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.registry.aliases import (
    confirm_reference_alias_group,
    confirm_safe_reference_alias_groups,
    list_reference_alias_candidates,
    list_reference_filter_options,
    reference_identity_ids,
    revoke_reference_alias_group,
)


async def test_alias_confirmation_groups_filters_and_analytics_without_rewriting_raw_values() -> (
    None
):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        path_reference = _reference(
            "Krea2\\realism_engine_krea2_v3.1.safetensors",
            "Krea2/realism_engine_krea2_v3.1.safetensors",
            occurrences=388,
        )
        plain_reference = _reference(
            "realism_engine_krea2_v3.1",
            "realism_engine_krea2_v3.1",
            occurrences=191,
        )
        session.add_all([path_reference, plain_reference])
        await session.flush()
        media = Media(kind="image", status="ready")
        session.add(media)
        await session.flush()
        snapshot = WorkflowSnapshot(
            media_id=media.id,
            reader_name="test",
            reader_version="1",
            source_carrier="test",
            evidence_sha256="a" * 64,
            raw_metadata={},
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
        )
        session.add(snapshot)
        await session.flush()
        session.add(
            ModelUsage(
                snapshot_id=snapshot.id,
                model_reference_id=path_reference.id,
                observation_type="lora_reference",
                pipeline_pattern="single_pass",
                slot="adapter",
                usage_order=0,
                confidence=1,
                evidence={},
            )
        )
        await session.commit()

        candidates = await list_reference_alias_candidates(session)
        assert len(candidates) == 1
        assert candidates[0].canonical_key == "realism_engine_krea2_v3.1"
        assert candidates[0].conflict_reason is None

        group = await confirm_reference_alias_group(
            session,
            reference_ids=[path_reference.id, plain_reference.id],
        )
        assert group.display_name == "realism_engine_krea2_v3.1"
        assert {reference.raw_value for reference in group.references} == {
            "Krea2\\realism_engine_krea2_v3.1.safetensors",
            "realism_engine_krea2_v3.1",
        }

        options = await list_reference_filter_options(session, reference_type="lora")
        assert len(options) == 1
        assert options[0].occurrence_count == 579
        assert options[0].alias_count == 2
        selected_ids = set(await session.scalars(reference_identity_ids(options[0].reference_id)))
        assert selected_ids == {path_reference.id, plain_reference.id}

        uses = await _load_model_uses(session, {media.id})
        assert uses[media.id][0].identity_key == f"reference_group:{group.id}"
        assert uses[media.id][0].identity_label == "realism_engine_krea2_v3.1"

        revoked = await revoke_reference_alias_group(session, group=group)
        assert revoked.status == "revoked"
        assert len(await list_reference_alias_candidates(session)) == 1
        assert len(await list_reference_filter_options(session, reference_type="lora")) == 2

    await engine.dispose()


async def test_alias_confirmation_rejects_references_linked_to_different_artifacts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        artifacts = [
            ModelArtifact(
                artifact_type="lora",
                display_name=f"Collision {index}",
                sha256=str(index) * 64,
                provider="test",
                identity_state="hash_verified",
                availability="present",
                enrichment_state="not_attempted",
            )
            for index in (1, 2)
        ]
        session.add_all(artifacts)
        await session.flush()
        references = [
            _reference(
                "one\\collision.safetensors",
                "one/collision.safetensors",
                occurrences=1,
                artifact_id=artifacts[0].id,
            ),
            _reference(
                "two\\collision.safetensors",
                "two/collision.safetensors",
                occurrences=1,
                artifact_id=artifacts[1].id,
            ),
        ]
        session.add_all(references)
        await session.commit()

        candidates = await list_reference_alias_candidates(session)
        assert candidates[0].conflict_reason is not None
        with pytest.raises(IngestionError, match="different artifacts"):
            await confirm_reference_alias_group(
                session,
                reference_ids=[reference.id for reference in references],
            )

    await engine.dispose()


async def test_same_artifact_aliases_are_confirmed_automatically() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        artifact = ModelArtifact(
            artifact_type="lora",
            display_name="Known adapter",
            sha256="a" * 64,
            provider="test",
            identity_state="hash_verified",
            availability="present",
            enrichment_state="not_attempted",
        )
        session.add(artifact)
        await session.flush()
        references = [
            _reference(
                "folder\\known_adapter.safetensors",
                "folder/known_adapter.safetensors",
                occurrences=3,
                artifact_id=artifact.id,
            ),
            _reference(
                "known_adapter",
                "known_adapter",
                occurrences=2,
                artifact_id=artifact.id,
            ),
        ]
        session.add_all(references)
        await session.commit()

        assert await confirm_safe_reference_alias_groups(session) == 1
        await session.commit()
        options = await list_reference_filter_options(session, reference_type="lora")
        assert len(options) == 1
        assert options[0].alias_count == 2

    await engine.dispose()


def _reference(
    raw_value: str,
    normalized_value: str,
    *,
    occurrences: int,
    artifact_id: UUID | None = None,
) -> ModelReference:
    return ModelReference(
        artifact_id=artifact_id,
        reference_type="lora",
        raw_value=raw_value,
        normalized_value=normalized_value,
        availability="missing",
        resolution_state="historical",
        occurrence_count=occurrences,
    )
