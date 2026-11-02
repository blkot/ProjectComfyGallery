from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_api.prompt_registry_schemas import (
    PromptRegistryEntryRequest,
    PromptRegistryImportRequest,
)
from comfy_gallery_api.routes.prompt_registry import (
    create_prompt_registry_entry,
    import_prompt_registry_entries,
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

            await create_prompt_registry_entry(
                PromptRegistryEntryRequest(
                    source="portraits",
                    index="0001",
                    prompt="A portrait",
                ),
                None,  # type: ignore[arg-type]
                session,
            )
            result = await lookup_prompt_registry_entry(
                None,  # type: ignore[arg-type]
                session,
                prompt_id="portraits - 1",
                limit=48,
                offset=0,
            )

            assert result.prompt_id == "portraits - 0001"
            assert result.entry is not None
            assert result.entry.index == "0001"
            assert result.total_media == 2
            assert {item.original_filename for item in result.media} == {
                "prompt-0.png",
                "prompt-1.png",
            }
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
