from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.evaluation_schemas import MediaFilterRequest
from comfy_gallery_api.main import app
from comfy_gallery_api.media_schemas import (
    MediaFavoriteUpdateRequest,
    MediaPageResponse,
    MediaPlaybackPreferenceUpdateRequest,
    MediaSpatialPreferenceUpdateRequest,
)
from comfy_gallery_api.routes.evaluations import _media_scope_query
from comfy_gallery_api.routes.media import (
    MediaSort,
    ReferenceMatch,
    get_media,
    get_media_navigation,
    list_media,
    update_media_favorite,
    update_media_playback_preference,
    update_media_spatial_preference,
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
        detail = await get_media(middle.id, None, session)
        assert detail.file_created_at == datetime.fromtimestamp(200, tz=UTC)
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


async def test_media_preferences_are_exposed_filterable_and_idempotent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        preferred = await _media_without_source(
            session,
            kind="image",
            filename="preferred.png",
            sha256="1" * 64,
        )
        untouched = await _media_without_source(
            session,
            kind="image",
            filename="untouched.png",
            sha256="2" * 64,
        )
        video = await _media_without_source(
            session,
            kind="video",
            filename="clip.mp4",
            sha256="3" * 64,
        )
        await session.commit()

        assert preferred.spatial_view_preferred is False
        assert preferred.favorite is False
        initial_page = await _library_page(session, sort="file_created_desc")
        assert all(item.spatial_view_preferred is False for item in initial_page.items)
        assert all(item.favorite is False for item in initial_page.items)
        initial_detail = await get_media(
            preferred.id,
            None,  # type: ignore[arg-type]
            session,
        )
        assert initial_detail.spatial_view_preferred is False
        assert initial_detail.prefer_spatial_playback is False
        assert initial_detail.spatial_available is False
        assert initial_detail.favorite is False

        first_spatial_response = await update_media_spatial_preference(
            preferred.id,
            MediaSpatialPreferenceUpdateRequest(spatial_view_preferred=True),
            None,  # type: ignore[arg-type]
            session,
        )
        repeated_spatial_response = await update_media_spatial_preference(
            preferred.id,
            MediaSpatialPreferenceUpdateRequest(spatial_view_preferred=True),
            None,  # type: ignore[arg-type]
            session,
        )
        favorite_response = await update_media_favorite(
            preferred.id,
            MediaFavoriteUpdateRequest(favorite=True),
            None,  # type: ignore[arg-type]
            session,
        )
        assert first_spatial_response.spatial_view_preferred is True
        assert first_spatial_response.prefer_spatial_playback is True
        assert repeated_spatial_response.spatial_view_preferred is True
        assert favorite_response.favorite is True

        await session.refresh(untouched)
        assert untouched.spatial_view_preferred is False
        assert untouched.favorite is False

        preferred_page = await _library_page(
            session,
            sort="file_created_desc",
            prefer_spatial_playback=True,
        )
        legacy_preferred_page = await _library_page(
            session,
            sort="file_created_desc",
            spatial_view_preferred=True,
        )
        favorite_page = await _library_page(
            session,
            sort="file_created_desc",
            favorite=True,
        )
        assert [item.id for item in preferred_page.items] == [preferred.id]
        assert [item.id for item in legacy_preferred_page.items] == [preferred.id]
        assert [item.id for item in favorite_page.items] == [preferred.id]
        assert preferred_page.items[0].favorite is True
        assert favorite_page.items[0].spatial_view_preferred is True

        reusable_scope_ids = list(
            await session.scalars(
                _media_scope_query(
                    MediaFilterRequest(
                        prefer_spatial_playback=True,
                        favorite=True,
                    ),
                    reviewable_only=False,
                )
            )
        )
        assert reusable_scope_ids == [preferred.id]

        with pytest.raises(ApiError) as conflicting_filter:
            await _library_page(
                session,
                sort="file_created_desc",
                prefer_spatial_playback=True,
                spatial_view_preferred=False,
            )
        assert conflicting_filter.value.code == "SPATIAL_PREFERENCE_FILTER_CONFLICT"

        with pytest.raises(ValueError):
            MediaFilterRequest(
                prefer_spatial_playback=True,
                spatial_view_preferred=False,
            )

        updated_detail = await get_media(
            preferred.id,
            None,  # type: ignore[arg-type]
            session,
        )
        assert updated_detail.spatial_view_preferred is True
        assert updated_detail.favorite is True

        for _ in range(2):
            response = await update_media_spatial_preference(
                preferred.id,
                MediaSpatialPreferenceUpdateRequest(spatial_view_preferred=False),
                None,  # type: ignore[arg-type]
                session,
            )
            assert response.spatial_view_preferred is False
            favorite_update = await update_media_favorite(
                preferred.id,
                MediaFavoriteUpdateRequest(favorite=False),
                None,  # type: ignore[arg-type]
                session,
            )
            assert favorite_update.favorite is False

        video_response = await update_media_playback_preference(
            video.id,
            MediaPlaybackPreferenceUpdateRequest(prefer_spatial_playback=True),
            None,  # type: ignore[arg-type]
            session,
        )
        assert video_response.prefer_spatial_playback is True
        assert video_response.spatial_view_preferred is True
        legacy_video_response = await update_media_spatial_preference(
            video.id,
            MediaSpatialPreferenceUpdateRequest(spatial_view_preferred=False),
            None,  # type: ignore[arg-type]
            session,
        )
        assert legacy_video_response.prefer_spatial_playback is False

        with pytest.raises(ApiError) as missing:
            await update_media_spatial_preference(
                uuid4(),
                MediaSpatialPreferenceUpdateRequest(spatial_view_preferred=True),
                None,  # type: ignore[arg-type]
                session,
            )
        assert missing.value.status_code == 404
        assert missing.value.code == "MEDIA_NOT_FOUND"

        with pytest.raises(ApiError) as missing_favorite:
            await update_media_favorite(
                uuid4(),
                MediaFavoriteUpdateRequest(favorite=True),
                None,  # type: ignore[arg-type]
                session,
            )
        assert missing_favorite.value.status_code == 404
        assert missing_favorite.value.code == "MEDIA_NOT_FOUND"

    await engine.dispose()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unauthenticated = await client.put(
            f"/api/v1/media/{uuid4()}/spatial-preference",
            json={"spatial_view_preferred": True},
        )
    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["error"]["code"] == "AUTH_REQUIRED"


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


async def _media_without_source(
    session: AsyncSession,
    *,
    kind: str,
    filename: str,
    sha256: str,
) -> Media:
    media = Media(kind=kind, status="ready")
    session.add(media)
    await session.flush()
    session.add(
        MediaAsset(
            media_id=media.id,
            sha256=sha256,
            byte_size=100,
            original_filename=filename,
            original_extension=f".{filename.rsplit('.', maxsplit=1)[-1]}",
            managed_path=f"managed/{filename}",
        )
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
    prefer_spatial_playback: bool | None = None,
    spatial_view_preferred: bool | None = None,
    spatial_available: bool | None = None,
    favorite: bool | None = None,
) -> MediaPageResponse:
    return await list_media(
        _principal=None,  # type: ignore[arg-type]
        session=session,
        kind=None,
        media_status=None,
        workflow_status=None,
        evaluation_state=None,
        trash=None,
        prefer_spatial_playback=prefer_spatial_playback,
        spatial_view_preferred=spatial_view_preferred,
        spatial_available=spatial_available,
        favorite=favorite,
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
