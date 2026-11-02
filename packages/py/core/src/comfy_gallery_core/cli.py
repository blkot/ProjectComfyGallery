import argparse
import asyncio
from pathlib import Path

import structlog

from comfy_gallery_core.auth import create_admin_if_missing
from comfy_gallery_core.config import get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.logging import configure_logging
from comfy_gallery_core.workflow.display_recovery import recover, register_command
from comfy_gallery_core.workflow.library_profiles import migrate_display
from comfy_gallery_core.workflow.prompt_index import rebuild_prompt_index


async def _create_admin(*, if_missing: bool) -> int:
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        json_logs=settings.environment != "development",
    )
    logger = structlog.get_logger(__name__)
    password = settings.admin_password
    if password is None:
        logger.error("admin_password_missing", env="CG_ADMIN_PASSWORD")
        return 2

    database = get_database()
    async with database.session() as session:
        user, created = await create_admin_if_missing(
            session,
            username=settings.admin_username,
            password=password.get_secret_value(),
        )
    await database.dispose()

    if not created and not if_missing:
        logger.error("admin_already_exists", username=user.username)
        return 1
    logger.info(
        "admin_ready",
        username=user.username,
        created=created,
    )
    return 0


async def _rebuild_prompt_index(*, batch_size: int) -> int:
    database = get_database()
    try:
        async with database.session() as session:
            processed = await rebuild_prompt_index(session, batch_size=batch_size)
    finally:
        await database.dispose()
    print(f"Rebuilt Prompt ID index for {processed} media records.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="comfy-gallery")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_admin = subparsers.add_parser("create-admin")
    create_admin.add_argument("--if-missing", action="store_true")
    register_command(subparsers)
    migrate = subparsers.add_parser(
        "migrate-display", help="Preview or install an offline library profile"
    )
    migrate.add_argument("--profile", type=Path, required=True)
    migrate.add_argument("--apply", action="store_true")
    rebuild_index = subparsers.add_parser(
        "rebuild-prompt-index", help="Backfill the materialized Prompt ID lookup index"
    )
    rebuild_index.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    if args.command == "create-admin":
        return asyncio.run(_create_admin(if_missing=args.if_missing))
    if args.command == "migrate-display":
        try:
            asyncio.run(migrate_display(args.profile, apply=args.apply))
        except ValueError as exc:
            parser.error(str(exc))
        return 0
    if args.command == "rebuild-prompt-index":
        if args.batch_size < 1:
            parser.error("--batch-size must be positive")
        return asyncio.run(_rebuild_prompt_index(batch_size=args.batch_size))
    if args.command == "recover-display":
        try:
            asyncio.run(recover(args))
        except ValueError as exc:
            parser.error(str(exc))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
