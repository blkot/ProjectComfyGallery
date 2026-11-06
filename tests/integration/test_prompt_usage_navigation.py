import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.routes.prompt_registry import (
    lookup_prompt_registry_entry,
    prompt_usage_navigation,
    prompt_usage_slideshow,
)
from comfy_gallery_core.db import Base
from comfy_gallery_core.db.models import (
    Media,
    MediaAsset,
    MediaPromptIndex,
    User,
    WorkflowSnapshot,
)
from comfy_gallery_core.evaluation.catalog import ensure_evaluation_catalog
from comfy_gallery_core.evaluation.service import ensure_media_evaluations
from comfy_gallery_core.workflow.display_fields import DISPLAY_KEY


def _ordered_ids(preferred: str | None = None) -> list[UUID]:
    groups = [1, 2, 0] if preferred == "beta" else [2, 1, 0]
    return [UUID(int=index) for group in groups for index in range(72, 0, -1) if index % 3 == group]


@pytest.fixture
async def usage_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            for index in [*range(1, 73), 1001]:
                session.add(
                    Media(
                        id=UUID(int=index),
                        kind="video" if index % 2 else "image",
                        status="ready",
                        favorite=index % 2 == 0,
                        created_at=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=index // 2),
                    )
                )
                session.add(
                    MediaAsset(
                        media_id=UUID(int=index),
                        sha256=f"{index:064x}",
                        byte_size=100,
                        original_filename=f"usage-{index}.png",
                        managed_path=f"managed/usage-{index}.png",
                    )
                )
                session.add(
                    MediaPromptIndex(
                        media_id=UUID(int=index),
                        source_key="scope" if index <= 72 else "unrelated",
                        index_key="1",
                        entry_index="0001",
                        prompt_id=f"{'scope' if index <= 72 else 'unrelated'} - 0001",
                        character_lora={0: None, 1: "beta", 2: "Alpha"}[index % 3],
                    )
                )
            await session.flush()
            reviewer = User(
                username="usage-reviewer",
                username_normalized="usage-reviewer",
                password_hash="test",
            )
            session.add(reviewer)
            await ensure_evaluation_catalog(session)
            media = await session.get(Media, UUID(int=5))
            assert media is not None
            evaluations = await ensure_media_evaluations(
                session, media=media, reviewer_user_id=reviewer.id, optional_modules=set()
            )
            next(row for row in evaluations if row.evaluation_kind == "base").is_trash = True
            await session.commit()
            yield session
    finally:
        await engine.dispose()


async def test_grouped_lookup_paginates_priority_without_filtering_or_workflow_loading(
    usage_session: AsyncSession,
) -> None:
    statements: list[str] = []

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    bind = usage_session.get_bind()
    event.listen(bind, "before_cursor_execute", record)
    try:
        first = await lookup_prompt_registry_entry(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="SCOPE - 1",
            group_by_character=True,
            preferred_character_lora=" BETA ",
            limit=48,
            offset=0,
        )
        second = await lookup_prompt_registry_entry(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="scope - 0001",
            group_by_character=True,
            preferred_character_lora="beta",
            limit=48,
            offset=48,
        )
    finally:
        event.remove(bind, "before_cursor_execute", record)

    assert first.entry is None  # Usage works for unregistered Prompt IDs too.
    assert first.total_media == second.total_media == 72
    assert [row.id for row in [*first.media, *second.media]] == _ordered_ids("beta")
    assert len(first.media) == 48 and len(second.media) == 24
    assert sum(row.is_trash for row in first.media) == 1
    assert {row.favorite for row in first.media} == {True, False}
    assert not any("workflow_snapshot.api_prompt" in statement for statement in statements)
    assert any("limit" in statement and "offset" in statement for statement in statements)

    default = await lookup_prompt_registry_entry(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        limit=48,
        offset=0,
    )
    assert [row.id for row in default.media] == [UUID(int=i) for i in range(72, 24, -1)]


@pytest.mark.parametrize("preferred", [None, "beta"])
async def test_navigation_matches_grouped_lookup_across_pages_and_at_boundaries(
    usage_session: AsyncSession, preferred: str | None
) -> None:
    expected = _ordered_ids(preferred)
    lookup = await lookup_prompt_registry_entry(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        group_by_character=True,
        preferred_character_lora=preferred,
        limit=200,
        offset=0,
    )
    assert [row.id for row in lookup.media] == expected
    for offset in [0, 23, 24, 47, 48, 71]:
        result = await prompt_usage_navigation(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="scope - 1",
            media_id=expected[offset],
            preferred_character_lora=preferred,
        )
        assert result.position == offset + 1
        assert result.total == 72
        assert result.previous_id == (expected[offset - 1] if offset else None)
        assert result.previous_position == (offset if offset else None)
        assert result.next_id == (expected[offset + 1] if offset < 71 else None)
        assert result.next_position == (offset + 2 if offset < 71 else None)


async def test_character_filter_scopes_lookup_navigation_and_slideshow(
    usage_session: AsyncSession,
) -> None:
    expected = [UUID(int=i) for i in range(71, 0, -3)]
    lookup = await lookup_prompt_registry_entry(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        character_lora=" ALPHA ",
        preferred_character_lora="beta",
        group_by_character=True,
        limit=48,
        offset=0,
    )
    assert lookup.total_media == 24
    assert [row.id for row in lookup.media] == expected
    navigation = await prompt_usage_navigation(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        media_id=expected[0],
        character_lora=" ALPHA ",
        preferred_character_lora="beta",
    )
    assert navigation.total == 24
    assert navigation.previous_id is None
    assert navigation.next_id == expected[1]
    slideshow = await prompt_usage_slideshow(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        character_lora=" ALPHA ",
        preferred_character_lora="beta",
        limit=2000,
    )
    assert [row.id for row in slideshow.items] == expected
    assert slideshow.total == 24
    assert slideshow.truncated is False


async def test_slideshow_starts_at_requested_media_beyond_the_initial_limit(
    usage_session: AsyncSession,
) -> None:
    expected = _ordered_ids("beta")
    result = await prompt_usage_slideshow(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="scope - 1",
        preferred_character_lora="beta",
        start_media_id=expected[50],
        limit=5,
    )
    assert [row.id for row in result.items] == expected[50:55]
    assert result.total == 72
    assert result.limit == 5
    assert result.truncated is True
    assert result.shuffle is False and result.random_seed is None
    for row in result.items:
        assert row.playback_url == f"/api/v1/media/{row.id}/playback"
        assert row.preview_url == f"/api/v1/media/{row.id}/preview"


@pytest.mark.parametrize("outside_id", [UUID(int=1001), UUID(int=9999), UUID(int=1)])
async def test_navigation_and_slideshow_reject_media_outside_prompt_character_scope(
    usage_session: AsyncSession, outside_id: UUID
) -> None:
    with pytest.raises(ApiError) as navigation_error:
        await prompt_usage_navigation(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="scope - 1",
            media_id=outside_id,
            character_lora="Alpha",
        )
    assert navigation_error.value.status_code == 404
    assert navigation_error.value.code == "MEDIA_NOT_IN_VIEW"
    with pytest.raises(ApiError) as slideshow_error:
        await prompt_usage_slideshow(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="scope - 1",
            start_media_id=outside_id,
            character_lora="Alpha",
            limit=2000,
        )
    assert slideshow_error.value.status_code == 404
    assert slideshow_error.value.code == "MEDIA_NOT_IN_VIEW"


async def test_usage_preserves_unindexed_workflow_evidence_fallback(
    usage_session: AsyncSession,
) -> None:
    packet = {"version": 1, "save_node_id": "3", "fields": {"prompt_id": "fallback - 5"}}
    usage_session.add(
        WorkflowSnapshot(
            media_id=UUID(int=1001),
            reader_name="test",
            reader_version="1",
            source_carrier="png",
            evidence_sha256="c" * 64,
            api_prompt_status="parsed",
            visual_workflow_status="absent",
            parse_status="parsed",
            api_prompt={
                "2": {"class_type": "Source", "inputs": {}},
                "3": {"class_type": "XantaSaveAndUpload", "inputs": {"cg_prompt_id": ["2", 1]}},
            },
            raw_metadata={"text_chunks": {DISPLAY_KEY: json.dumps(packet)}},
        )
    )
    index = await usage_session.get(MediaPromptIndex, UUID(int=1001))
    assert index is not None
    await usage_session.delete(index)
    await usage_session.commit()
    result = await prompt_usage_navigation(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="fallback - 0005",
        media_id=UUID(int=1001),
    )
    assert result.position == result.total == 1
    assert result.previous_id is None and result.next_id is None
    playlist = await prompt_usage_slideshow(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="fallback - 5",
        limit=2000,
    )
    assert [row.id for row in playlist.items] == [UUID(int=1001)]


async def test_empty_usage_returns_empty_playlist_and_invalid_identifier_is_rejected(
    usage_session: AsyncSession,
) -> None:
    result = await prompt_usage_slideshow(
        None,  # type: ignore[arg-type]
        usage_session,
        prompt_id="absent - 1",
        limit=2000,
    )
    assert result.items == [] and result.total == 0 and result.truncated is False
    with pytest.raises(ApiError) as error:
        await prompt_usage_navigation(
            None,  # type: ignore[arg-type]
            usage_session,
            prompt_id="invalid",
            media_id=UUID(int=1),
        )
    assert error.value.status_code == 422
    assert error.value.code == "PROMPT_ID_INVALID"
