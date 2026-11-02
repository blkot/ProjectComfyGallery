from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.prompt_registry_schemas import (
    PromptRegistryEntryRequest,
    PromptRegistryImportRequest,
)
from comfy_gallery_api.routes.prompt_registry import (
    create_prompt_registry_entry,
    import_prompt_registry_entries,
    list_prompt_registry_sources,
    lookup_prompt_registry_entry,
)
from comfy_gallery_core.db import Base
from comfy_gallery_core.db.models import (
    Media,
    MediaAsset,
    WorkflowDisplayProfile,
    WorkflowSnapshot,
)
from comfy_gallery_core.workflow.display_fields import topology
from comfy_gallery_core.workflow.prompt_index import rebuild_prompt_index


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
