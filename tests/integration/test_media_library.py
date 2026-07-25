from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comfy_gallery_api.evaluation_schemas import MediaFilterRequest
from comfy_gallery_api.media_schemas import MediaPageResponse
from comfy_gallery_api.routes.evaluations import _media_scope_query
from comfy_gallery_api.routes.media import (
    MediaSort,
    ReferenceMatch,
    get_media_navigation,
    list_media,
)
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    Media,
    MediaAsset,
    ModelReference,
    ModelReferenceGroup,
    ModelUsage,
    ScanBatch,
    SourceOccurrence,
    SourceRoot,
    WorkflowSnapshot,
)


async def test_media_library_sorts_by_source_time_and_filters_model_usages() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        root = SourceRoot(name="test", path="/imports")
        session.add(root)
        await session.flush()
        scan = ScanBatch(source_root_id=root.id, status="completed")
        session.add(scan)
        await session.flush()

        oldest = await _media_with_source(
            session,
            root=root,
            scan=scan,
            filename="oldest.png",
            sha256="a" * 64,
            mtime_seconds=100,
            imported_seconds=500,
        )
        newest = await _media_with_source(
            session,
            root=root,
            scan=scan,
            filename="newest.png",
            sha256="b" * 64,
            mtime_seconds=300,
            imported_seconds=600,
        )
        middle = await _media_with_source(
            session,
            root=root,
            scan=scan,
            filename="middle.png",
            sha256="c" * 64,
            mtime_seconds=200,
            imported_seconds=700,
        )
        uploaded = Media(
            kind="image",
            status="ready",
            created_at=datetime.fromtimestamp(250, tz=UTC),
        )
        session.add(uploaded)
        await session.flush()
        session.add(
            MediaAsset(
                media_id=uploaded.id,
                sha256="f" * 64,
                byte_size=250,
                original_filename="uploaded.png",
                original_extension=".png",
                managed_path="managed/uploaded.png",
            )
        )
        checkpoint = ModelReference(
            reference_type="checkpoint",
            raw_value="krea2.safetensors",
            normalized_value="krea2.safetensors",
            availability="present",
            resolution_state="resolved",
            occurrence_count=1,
        )
        lora = ModelReference(
            reference_type="lora",
            raw_value="character_000003500",
            normalized_value="character_000003500",
            availability="present",
            resolution_state="resolved",
            occurrence_count=1,
        )
        lora_alias = ModelReference(
            reference_type="lora",
            raw_value="Krea2\\character_000003500.safetensors",
            normalized_value="Krea2/character_000003500.safetensors",
            availability="present",
            resolution_state="resolved",
            occurrence_count=1,
        )
        second_lora = ModelReference(
            reference_type="lora",
            raw_value="lighting_style.safetensors",
            normalized_value="lighting_style.safetensors",
            availability="present",
            resolution_state="resolved",
            occurrence_count=2,
        )
        identity_group = ModelReferenceGroup(
            reference_type="lora",
            canonical_key="character_000003500",
            display_name="character_000003500",
            source="manual_alias",
            confidence=1,
            status="confirmed",
        )
        session.add_all([checkpoint, lora, lora_alias, second_lora, identity_group])
        await session.flush()
        lora.identity_group_id = identity_group.id
        lora_alias.identity_group_id = identity_group.id
        snapshot = WorkflowSnapshot(
            media_id=middle.id,
            reader_name="test",
            reader_version="1",
            source_carrier="test",
            evidence_sha256="d" * 64,
            raw_metadata={},
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
        )
        session.add(snapshot)
        await session.flush()
        session.add_all(
            [
                _usage(snapshot.id, checkpoint.id, "checkpoint_reference", 0),
                _usage(snapshot.id, lora_alias.id, "lora_reference", 1),
                _usage(snapshot.id, second_lora.id, "lora_reference", 2),
            ]
        )
        newest_snapshot = WorkflowSnapshot(
            media_id=newest.id,
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
        session.add(newest_snapshot)
        await session.flush()
        session.add(_usage(newest_snapshot.id, second_lora.id, "lora_reference", 0))
        await session.commit()

        page = await _library_page(session, sort="file_created_desc")
        assert [item.id for item in page.items] == [
            newest.id,
            uploaded.id,
            middle.id,
            oldest.id,
        ]
        assert [item.file_created_at for item in page.items] == [
            datetime.fromtimestamp(300, tz=UTC),
            datetime.fromtimestamp(250, tz=UTC),
            datetime.fromtimestamp(200, tz=UTC),
            datetime.fromtimestamp(100, tz=UTC),
        ]
        assert [item.id for item in (await _library_page(session, sort="filename_asc")).items] == [
            middle.id,
            newest.id,
            oldest.id,
            uploaded.id,
        ]
        assert [item.id for item in (await _library_page(session, sort="size_asc")).items] == [
            oldest.id,
            middle.id,
            uploaded.id,
            newest.id,
        ]
        assert [item.id for item in (await _library_page(session, sort="imported_desc")).items] == [
            middle.id,
            newest.id,
            oldest.id,
            uploaded.id,
        ]

        filtered = await _library_page(
            session,
            sort="file_created_desc",
            checkpoint_reference_ids=[checkpoint.id],
            lora_reference_ids=[lora.id],
        )
        assert [item.id for item in filtered.items] == [middle.id]

        any_lora = await _library_page(
            session,
            sort="file_created_desc",
            lora_reference_ids=[lora.id, second_lora.id],
            lora_reference_match="any",
        )
        assert [item.id for item in any_lora.items] == [newest.id, middle.id]

        all_loras = await _library_page(
            session,
            sort="file_created_desc",
            lora_reference_ids=[lora.id, second_lora.id],
            lora_reference_match="all",
        )
        assert [item.id for item in all_loras.items] == [middle.id]

        saved_scope_ids = list(
            await session.scalars(
                _media_scope_query(
                    MediaFilterRequest(
                        checkpoint_reference_ids=[checkpoint.id],
                        lora_reference_ids=[lora.id, second_lora.id],
                        lora_reference_match="all",
                    )
                )
            )
        )
        assert saved_scope_ids == [middle.id]

        navigation = await get_media_navigation(
            media_id=middle.id,
            _principal=None,  # type: ignore[arg-type]
            session=session,
            kind=None,
            media_status=None,
            workflow_status=None,
            evaluation_state=None,
            trash=None,
            source_root_id=None,
            checkpoint_reference_id=None,
            checkpoint_reference_match="any",
            lora_reference_id=None,
            lora_reference_match="any",
            sort="file_created_desc",
        )
        assert navigation.position == 3
        assert navigation.total == 4
        assert navigation.previous_id == uploaded.id
        assert navigation.previous_position == 2
        assert navigation.next_id == oldest.id
        assert navigation.next_position == 4

    await engine.dispose()


async def _media_with_source(
    session: AsyncSession,
    *,
    root: SourceRoot,
    scan: ScanBatch,
    filename: str,
    sha256: str,
    mtime_seconds: int,
    imported_seconds: int,
) -> Media:
    media = Media(
        kind="image",
        status="ready",
        created_at=datetime.fromtimestamp(imported_seconds, tz=UTC),
    )
    session.add(media)
    await session.flush()
    session.add_all(
        [
            MediaAsset(
                media_id=media.id,
                sha256=sha256,
                byte_size=mtime_seconds,
                original_filename=filename,
                original_extension=".png",
                managed_path=f"managed/{filename}",
            ),
            SourceOccurrence(
                source_root_id=root.id,
                media_id=media.id,
                relative_path=filename,
                original_filename=filename,
                byte_size=mtime_seconds,
                mtime_ns=mtime_seconds * 1_000_000_000,
                sha256=sha256,
                status="present",
                first_seen_scan_id=scan.id,
                last_seen_scan_id=scan.id,
            ),
        ]
    )
    return media


async def _library_page(
    session: AsyncSession,
    *,
    sort: MediaSort,
    checkpoint_reference_ids: list[UUID] | None = None,
    checkpoint_reference_match: ReferenceMatch = "any",
    lora_reference_ids: list[UUID] | None = None,
    lora_reference_match: ReferenceMatch = "any",
) -> MediaPageResponse:
    return await list_media(
        _principal=None,  # type: ignore[arg-type]
        session=session,
        kind=None,
        media_status=None,
        workflow_status=None,
        evaluation_state=None,
        trash=None,
        source_root_id=None,
        checkpoint_reference_id=checkpoint_reference_ids,
        checkpoint_reference_match=checkpoint_reference_match,
        lora_reference_id=lora_reference_ids,
        lora_reference_match=lora_reference_match,
        sort=sort,
        limit=48,
        offset=0,
    )


def _usage(
    snapshot_id: UUID,
    reference_id: UUID,
    observation_type: str,
    order: int,
) -> ModelUsage:
    return ModelUsage(
        snapshot_id=snapshot_id,
        model_reference_id=reference_id,
        observation_type=observation_type,
        pipeline_pattern="single_pass",
        slot="single",
        usage_order=order,
        confidence=1,
        evidence={},
    )
