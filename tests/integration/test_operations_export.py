import json
import zipfile

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.config import Settings
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import ApiToken, ExportRun, Media, MediaAsset, User
from comfy_gallery_core.media.errors import IngestionError
from comfy_gallery_core.operations.exports import (
    EXPORT_SCHEMA_VERSION,
    create_portable_export,
    safe_export_path,
)


async def test_portable_export_preserves_user_data_and_excludes_auth_secrets(
    tmp_path,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    settings = Settings(
        environment="test",
        managed_root=tmp_path / "managed",
        staging_root=tmp_path / "staging",
        export_root=tmp_path / "exports",
        backup_root=tmp_path / "backups",
        runtime_root=tmp_path / "runtime",
        allowed_source_roots=str(tmp_path / "imports"),
        minimum_free_bytes=0,
    )
    async with session_factory() as session:
        user = User(
            username="operator",
            username_normalized="operator",
            password_hash="secret-password-hash",
        )
        media = Media(kind="image", status="ready")
        session.add_all([user, media])
        await session.flush()
        session.add(
            ApiToken(
                user_id=user.id,
                label="must-not-export",
                token_prefix="cg_live_",
                token_hash="secret-api-token-hash",
            )
        )
        session.add(
            MediaAsset(
                media_id=media.id,
                sha256="a" * 64,
                byte_size=123,
                original_filename="private.png",
                original_extension="png",
                managed_path="originals/aa/private.png",
            )
        )
        export_run = ExportRun(
            created_by_user_id=user.id,
            requested_options={"include_workflow_evidence": True},
        )
        session.add(export_run)
        await session.commit()

        await create_portable_export(
            session,
            export_run=export_run,
            settings=settings,
        )
        assert export_run.status == "succeeded"
        assert export_run.artifact_path is not None
        archive_path = safe_export_path(settings, export_run.artifact_path)
        assert archive_path.is_file()

        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            assert "manifest.json" in names
            assert "jsonl/principals.jsonl" in names
            assert "jsonl/media.jsonl" in names
            assert "jsonl/media_asset.jsonl" in names
            assert "csv/evaluation_scores.csv" in names
            assert "jsonl/api_token.jsonl" not in names
            assert "jsonl/web_session.jsonl" not in names
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["export_schema_version"] == EXPORT_SCHEMA_VERSION
            assert manifest["contents"]["counts"]["media"] == 1
            principals = archive.read("jsonl/principals.jsonl").decode()
            media_assets = archive.read("jsonl/media_asset.jsonl").decode()
            assert "operator" in principals
            assert "secret-password-hash" not in principals
            assert "secret-api-token-hash" not in principals
            assert "private.png" in media_assets

    await engine.dispose()


async def test_workflow_evidence_can_be_omitted_from_portable_export(tmp_path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(
        environment="test",
        export_root=tmp_path / "exports",
        minimum_free_bytes=0,
    )
    async with session_factory() as session:
        user = User(username="operator", username_normalized="operator", password_hash="x")
        session.add(user)
        await session.flush()
        export_run = ExportRun(
            created_by_user_id=user.id,
            requested_options={"include_workflow_evidence": False},
        )
        session.add(export_run)
        await session.commit()
        await create_portable_export(
            session,
            export_run=export_run,
            settings=settings,
        )
        assert export_run.artifact_path is not None
        with zipfile.ZipFile(safe_export_path(settings, export_run.artifact_path)) as archive:
            assert "jsonl/workflow_snapshot.jsonl" not in archive.namelist()
            assert "jsonl/model_artifact.jsonl" in archive.namelist()
    await engine.dispose()


def test_export_path_cannot_escape_configured_root(tmp_path) -> None:
    settings = Settings(export_root=tmp_path / "exports")
    with pytest.raises(IngestionError, match="outside"):
        safe_export_path(settings, "../private.zip")
