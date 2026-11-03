import json
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.prompt_registry_schemas import (
    PromptRegistryEntryRequest,
    PromptRegistryImportRequest,
)
from comfy_gallery_api.routes.prompt_registry import (
    _enforce_import_body_size,
    _filter_media_by_character,
    create_prompt_registry_entry,
    import_prompt_registry_entries,
    list_prompt_registry_character_loras,
    list_prompt_registry_sources,
    lookup_prompt_registry_entry,
    prompt_registry_heatmap,
    prompt_registry_neighbor,
    prompt_registry_stats,
    random_prompt_registry_entry,
)
from comfy_gallery_core.db import Base
from comfy_gallery_core.db.models import (
    Media,
    MediaAsset,
    MediaPromptIndex,
    User,
    WorkflowDisplayProfile,
    WorkflowSnapshot,
)
from comfy_gallery_core.evaluation.catalog import ensure_evaluation_catalog
from comfy_gallery_core.evaluation.service import ensure_media_evaluations
from comfy_gallery_core.workflow.display_fields import DISPLAY_KEY, topology
from comfy_gallery_core.workflow.prompt_index import (
    rebuild_prompt_index,
    sync_media_prompt_index,
)


async def test_prompt_registry_lookup_prefers_visual_show_text_and_returns_all_media() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            workflow_id = str(uuid4())
            api = {
                "847": {
                    "class_type": "XantaPromptLibrary",
                    "inputs": {"library": "portraits"},
                },
                "827": {
                    "class_type": "ShowText|pysssss",
                    "inputs": {"text": ["847", 1], "text_0": "stale - 0001"},
                },
            }
            profile = WorkflowDisplayProfile(
                scope=f"workflow:{workflow_id}",
                topology_sha256=topology(api),
                reference_media_id=uuid4(),
                bindings={"prompt_id": "827"},
            )
            session.add(profile)
            for index in range(2):
                media = Media(id=uuid4(), kind="image", status="ready")
                session.add(media)
                await session.flush()
                session.add(
                    MediaAsset(
                        media_id=media.id,
                        sha256=f"{index + 1}" * 64,
                        byte_size=100,
                        original_filename=f"prompt-{index}.png",
                        managed_path=f"managed/prompt-{index}.png",
                    )
                )
                session.add(
                    WorkflowSnapshot(
                        media_id=media.id,
                        reader_name="test",
                        reader_version="1",
                        source_carrier="png",
                        evidence_sha256=f"{index + 3}" * 64,
                        api_prompt_status="parsed",
                        visual_workflow_status="parsed",
                        parse_status="parsed",
                        api_prompt=api,
                        visual_workflow={
                            "id": workflow_id,
                            "nodes": [
                                {
                                    "id": "827",
                                    "type": "ShowText|pysssss",
                                    "widgets_values": ["portraits - 0001"],
                                }
                            ],
                        },
                    )
                )
            await session.commit()

            assert await rebuild_prompt_index(session) == 2

            await create_prompt_registry_entry(
                PromptRegistryEntryRequest(
                    source="portraits",
                    index="0001",
                    prompt="A portrait",
                ),
                None,  # type: ignore[arg-type]
                session,
            )
            lookup_statements: list[str] = []

            def record_lookup_statement(
                _connection, _cursor, statement, _parameters, _context, _executemany
            ):
                lookup_statements.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", record_lookup_statement)
            try:
                result = await lookup_prompt_registry_entry(
                    None,  # type: ignore[arg-type]
                    session,
                    prompt_id="portraits - 1",
                    limit=48,
                    offset=0,
                )
            finally:
                event.remove(
                    engine.sync_engine,
                    "before_cursor_execute",
                    record_lookup_statement,
                )

            assert result.prompt_id == "portraits - 0001"
            assert result.entry is not None
            assert result.entry.index == "0001"
            assert result.total_media == 2
            assert {item.original_filename for item in result.media} == {
                "prompt-0.png",
                "prompt-1.png",
            }
            assert not any(
                "left outer join workflow_snapshot" in statement.lower()
                for statement in lookup_statements
            )

            stored_media = list(await session.scalars(select(Media).order_by(Media.id)))
            reviewer = User(
                username="prompt-lookup-reviewer",
                username_normalized="prompt-lookup-reviewer",
                password_hash="test",
            )
            session.add(reviewer)
            await ensure_evaluation_catalog(session)
            evaluations = await ensure_media_evaluations(
                session,
                media=stored_media[0],
                reviewer_user_id=reviewer.id,
                optional_modules=set(),
            )
            next(
                evaluation for evaluation in evaluations if evaluation.evaluation_kind == "base"
            ).is_trash = True
            await session.commit()

            trashed_lookup = await lookup_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                prompt_id="portraits - 1",
                limit=48,
                offset=0,
            )
            assert trashed_lookup.total_media == 2
            assert sum(item.is_trash for item in trashed_lookup.media) == 1
            assert all(item.favorite is False for item in trashed_lookup.media)
            imported = await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="portraits",
                            index="0002",
                            prompt="Another portrait",
                        )
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )
            assert imported.created_count == 1
            assert imported.entries[0].index == "0002"
    finally:
        await engine.dispose()


async def test_prompt_registry_import_returns_rows_after_commit() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=True)() as session:
            result = await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="0001",
                            prompt="A test prompt",
                        )
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )

            assert result.created_count == 1
            assert result.updated_count == 0
            assert result.entries[0].source == "xanta-utils"
            assert result.entries[0].index == "0001"
            assert result.entries[0].created_at is not None
            assert result.entries[0].updated_at is not None
    finally:
        await engine.dispose()


async def test_prompt_registry_import_uses_a_bounded_number_of_sql_statements() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    statements: list[str] = []

    def record_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", record_statement)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        statements.clear()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            entries = [
                PromptRegistryEntryRequest(
                    source="xanta-utils",
                    index=f"{index:05d}",
                    prompt=f"Prompt {index}",
                )
                for index in range(200)
            ]
            result = await import_prompt_registry_entries(
                PromptRegistryImportRequest(entries=entries),
                None,  # type: ignore[arg-type]
                session,
            )

            assert result.created_count == 200
            assert result.updated_count == 0
            assert len(result.entries) == 200

        # One read for existing keys, one bulk upsert, and one read for the
        # committed response. This guards against regressing to one query per row.
        assert len(statements) <= 4

        statements.clear()
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            repeated = await import_prompt_registry_entries(
                PromptRegistryImportRequest(entries=entries),
                None,  # type: ignore[arg-type]
                session,
            )
            assert repeated.created_count == 0
            assert repeated.updated_count == 200
        assert len(statements) <= 4
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record_statement)
        await engine.dispose()


async def test_prompt_registry_import_rejects_duplicate_keys_in_one_batch() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            request = PromptRegistryImportRequest(
                entries=[
                    PromptRegistryEntryRequest(
                        source="xanta-utils",
                        index="00001",
                        prompt="first",
                    ),
                    PromptRegistryEntryRequest(
                        source="XANTA-UTILS",
                        index="00001",
                        prompt="duplicate",
                    ),
                ]
            )

            with pytest.raises(ApiError, match="duplicate") as raised:
                await import_prompt_registry_entries(
                    request,
                    None,  # type: ignore[arg-type]
                    session,
                )

            assert raised.value.status_code == 422
            assert raised.value.code == "DUPLICATE_PROMPT_REGISTRY_KEY"
    finally:
        await engine.dispose()


async def test_prompt_registry_sources_are_distinct_and_source_only() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="00001",
                            prompt="portrait prompt",
                        ),
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="00002",
                            prompt="another portrait prompt",
                        ),
                        PromptRegistryEntryRequest(
                            source="other-library",
                            index="00001",
                            prompt="portrait prompt from another source",
                        ),
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )

            assert await list_prompt_registry_sources(
                None,  # type: ignore[arg-type]
                session,
                q="xan",
                limit=24,
            ) == ["xanta-utils"]
            assert (
                await list_prompt_registry_sources(
                    None,  # type: ignore[arg-type]
                    session,
                    q="prompt",
                    limit=24,
                )
                == []
            )
    finally:
        await engine.dispose()


async def test_prompt_registry_random_stats_and_neighbors_use_materialized_index() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="00001",
                            prompt="Materialized",
                        ),
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="00002",
                            prompt="Unmaterialized two",
                        ),
                        PromptRegistryEntryRequest(
                            source="xanta-utils",
                            index="00010",
                            prompt="Unmaterialized ten",
                        ),
                        PromptRegistryEntryRequest(
                            source="other",
                            index="00001",
                            prompt="Other source",
                        ),
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )
            media = Media(id=uuid4(), kind="image", status="ready", favorite=True)
            ordinary_media = Media(id=uuid4(), kind="image", status="ready")
            trashed_media = Media(
                id=uuid4(),
                kind="image",
                status="ready",
                favorite=True,
            )
            session.add_all([media, ordinary_media, trashed_media])
            await session.flush()
            reviewer = User(
                username="prompt-registry-reviewer",
                username_normalized="prompt-registry-reviewer",
                password_hash="test",
            )
            session.add(reviewer)
            await ensure_evaluation_catalog(session)
            evaluations = await ensure_media_evaluations(
                session,
                media=trashed_media,
                reviewer_user_id=reviewer.id,
                optional_modules=set(),
            )
            base_evaluation = next(
                evaluation for evaluation in evaluations if evaluation.evaluation_kind == "base"
            )
            base_evaluation.is_trash = True
            session.add_all(
                [
                    MediaPromptIndex(
                        media_id=media.id,
                        source_key="xanta-utils",
                        entry_index="00001",
                        index_key="1",
                        prompt_id="xanta-utils - 00001",
                        evidence_source="save_node",
                    ),
                    MediaPromptIndex(
                        media_id=ordinary_media.id,
                        source_key="xanta-utils",
                        entry_index="00002",
                        index_key="2",
                        prompt_id="xanta-utils - 00002",
                        evidence_source="save_node",
                    ),
                    MediaPromptIndex(
                        media_id=trashed_media.id,
                        source_key="xanta-utils",
                        entry_index="00010",
                        index_key="10",
                        prompt_id="xanta-utils - 00010",
                        evidence_source="save_node",
                    ),
                ]
            )
            await session.commit()

            stats = await prompt_registry_stats(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
            )
            assert stats.source == "xanta-utils"
            assert stats.source_count == 1
            assert stats.registered_count == 3
            assert stats.materialized_count == 1
            assert stats.unmaterialized_count == 2

            heatmap = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                limit=2,
                offset=1,
            )
            assert heatmap.total == 3
            assert heatmap.limit == 2
            assert heatmap.offset == 1
            assert heatmap.max_media_count == 1
            assert [(item.index, item.media_count) for item in heatmap.items] == [
                ("00002", 0),
                ("00010", 0),
            ]

            favorites_only = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                limit=20_000,
                offset=0,
            )
            assert [(item.index, item.media_count) for item in favorites_only.items] == [
                ("00001", 1),
                ("00002", 0),
                ("00010", 0),
            ]

            with_not_faved = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                include_not_faved=True,
                limit=20_000,
                offset=0,
            )
            assert [(item.index, item.media_count) for item in with_not_faved.items] == [
                ("00001", 1),
                ("00002", 1),
                ("00010", 0),
            ]

            with_trash = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                include_trash=True,
                limit=20_000,
                offset=0,
            )
            assert [(item.index, item.media_count) for item in with_trash.items] == [
                ("00001", 1),
                ("00002", 0),
                ("00010", 1),
            ]

            full_scope = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                include_not_faved=True,
                include_trash=True,
                limit=20_000,
                offset=0,
            )
            assert [(item.index, item.media_count) for item in full_scope.items] == [
                ("00001", 1),
                ("00002", 1),
                ("00010", 1),
            ]

            random_any = await random_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                source=None,
                materialization="any",
            )
            assert random_any.index in {"00001", "00002", "00010"}

            random_unmaterialized = await random_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                materialization="unmaterialized",
            )
            assert random_unmaterialized.index in {"00002", "00010"}
            assert random_unmaterialized.media_count == 0
            assert random_unmaterialized.materialization == "unmaterialized"

            random_materialized = await random_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                materialization="materialized",
            )
            assert random_materialized.index == "00001"
            assert random_materialized.media_count == 1
            assert random_materialized.materialization == "materialized"

            with pytest.raises(ApiError, match="No prompt matches") as random_raised:
                await random_prompt_registry_entry(
                    None,  # type: ignore[arg-type]
                    session,
                    source="missing",
                    materialization="unmaterialized",
                )
            assert random_raised.value.status_code == 404
            assert random_raised.value.code == "PROMPT_REGISTRY_RANDOM_NOT_FOUND"

            next_entry = await prompt_registry_neighbor(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                index="00001",
                direction="next",
            )
            assert next_entry.entry.index == "00002"

            previous_entry = await prompt_registry_neighbor(
                None,  # type: ignore[arg-type]
                session,
                source="xanta-utils",
                index="00010",
                direction="previous",
            )
            assert previous_entry.entry.index == "00002"

            with pytest.raises(ApiError, match="No registered neighbor") as raised:
                await prompt_registry_neighbor(
                    None,  # type: ignore[arg-type]
                    session,
                    source="xanta-utils",
                    index="00001",
                    direction="previous",
                )
            assert raised.value.status_code == 404
            assert raised.value.code == "PROMPT_REGISTRY_NEIGHBOR_NOT_FOUND"
    finally:
        await engine.dispose()


async def test_prompt_registry_supports_128_digit_indexes_without_integer_casts() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            stored_index = "0" + ("9" * 127)
            await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="large-library",
                            index=stored_index,
                            prompt="An arbitrary precision prompt",
                        )
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )

            result = await lookup_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                prompt_id=f"large-library - {'9' * 127}",
                limit=48,
                offset=0,
            )

            assert result.entry is not None
            assert result.entry.index == stored_index
            assert result.prompt_id == f"large-library - {stored_index}"
    finally:
        await engine.dispose()


async def test_prompt_registry_import_size_check_uses_received_body_bytes() -> None:
    body = b"{" + (b" " * (8 * 1024 * 1024)) + b"}"

    async def receive() -> dict[str, object]:
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/prompt-registry/import",
            "headers": [],
        },
        receive,
    )

    with pytest.raises(ApiError) as raised:
        await _enforce_import_body_size(request)

    assert raised.value.status_code == 413
    assert raised.value.code == "PROMPT_REGISTRY_IMPORT_TOO_LARGE"


async def test_prompt_registry_character_lora_filter_and_options() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            await import_prompt_registry_entries(
                PromptRegistryImportRequest(
                    entries=[
                        PromptRegistryEntryRequest(
                            source="character-src",
                            index="00001",
                            prompt="First",
                        ),
                        PromptRegistryEntryRequest(
                            source="character-src",
                            index="00002",
                            prompt="Second",
                        ),
                        PromptRegistryEntryRequest(
                            source="character-src",
                            index="00003",
                            prompt="Never generated with a character",
                        ),
                    ]
                ),
                None,  # type: ignore[arg-type]
                session,
            )
            first = Media(id=uuid4(), kind="image", status="ready", favorite=True)
            second = Media(id=uuid4(), kind="image", status="ready", favorite=True)
            session.add_all([first, second])
            await session.flush()
            session.add_all(
                [
                    MediaPromptIndex(
                        media_id=first.id,
                        source_key="character-src",
                        entry_index="00001",
                        index_key="1",
                        prompt_id="character-src - 00001",
                        evidence_source="save_node",
                        character_lora="Character_A_v1",
                    ),
                    MediaPromptIndex(
                        media_id=second.id,
                        source_key="character-src",
                        entry_index="00002",
                        index_key="2",
                        prompt_id="character-src - 00002",
                        evidence_source="save_node",
                        character_lora="Character_B_v1",
                    ),
                ]
            )
            await session.commit()

            heatmap = await prompt_registry_heatmap(
                None,  # type: ignore[arg-type]
                session,
                source="character-src",
                character_lora="character_a_v1",
                limit=20_000,
                offset=0,
            )
            assert [(item.index, item.media_count) for item in heatmap.items] == [
                ("00001", 1),
                ("00002", 0),
                ("00003", 0),
            ]

            options = await list_prompt_registry_character_loras(
                None,  # type: ignore[arg-type]
                session,
                q=None,
                limit=50,
            )
            assert {(option.name, option.media_count) for option in options} == {
                ("Character_A_v1", 1),
                ("Character_B_v1", 1),
            }

            stats = await prompt_registry_stats(
                None,  # type: ignore[arg-type]
                session,
                source="character-src",
                character_lora="Character_A_v1",
            )
            # Character LoRA scopes the favorite signal, not the prompt universe:
            # a prompt never generated with the character stays unmaterialized.
            assert (
                stats.registered_count,
                stats.materialized_count,
                stats.unmaterialized_count,
            ) == (3, 1, 2)

            unpicked = await random_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                source="character-src",
                character_lora="Character_A_v1",
                materialization="unmaterialized",
            )
            assert unpicked.index in {"00002", "00003"}

            picked = await random_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                source="character-src",
                character_lora="Character_B_v1",
                materialization="materialized",
            )
            assert picked.index == "00002"

            filtered = await _filter_media_by_character(
                session,
                [(first, None), (second, None)],  # type: ignore[list-item]
                "character_a_v1",
            )
            assert [media.id for media, _asset in filtered] == [first.id]
    finally:
        await engine.dispose()


async def test_sync_materializes_character_lora_from_the_save_packet() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            media = Media(id=uuid4(), kind="image", status="ready")
            session.add(media)
            await session.flush()
            session.add(
                MediaAsset(
                    media_id=media.id,
                    sha256="a" * 64,
                    byte_size=1,
                    original_filename="character.png",
                    managed_path="managed/character.png",
                )
            )
            api = {
                "2": {"class_type": "Source", "inputs": {}},
                "3": {
                    "class_type": "XantaSaveAndUpload",
                    "inputs": {
                        "cg_prompt_id": ["2", 1],
                        "cg_character_lora": ["2", 0],
                    },
                },
            }
            packet = {
                "version": 1,
                "save_node_id": "3",
                "fields": {
                    "prompt_id": "character-src - 00001",
                    "character_lora": " Character_A_v1 ",
                },
            }
            session.add(
                WorkflowSnapshot(
                    media_id=media.id,
                    reader_name="test",
                    reader_version="1",
                    source_carrier="png",
                    evidence_sha256="b" * 64,
                    api_prompt_status="parsed",
                    visual_workflow_status="parsed",
                    parse_status="parsed",
                    api_prompt=api,
                    raw_metadata={"text_chunks": {DISPLAY_KEY: json.dumps(packet)}},
                )
            )
            await session.commit()

            record = await sync_media_prompt_index(session, media_id=media.id)

            assert record.prompt_id == "character-src - 00001"
            assert record.character_lora == "Character_A_v1"
    finally:
        await engine.dispose()
