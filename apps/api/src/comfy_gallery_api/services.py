import os

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_api.schemas import ServiceCheck
from comfy_gallery_core.config import Settings


async def check_database(session: AsyncSession) -> ServiceCheck:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        return ServiceCheck(status="error", detail="database unavailable")
    return ServiceCheck(status="ok")


async def check_redis(redis_url: str) -> ServiceCheck:
    client = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        await client.ping()
    except Exception:
        return ServiceCheck(status="error", detail="redis unavailable")
    finally:
        await client.aclose()
    return ServiceCheck(status="ok")


def check_storage(settings: Settings) -> ServiceCheck:
    required_paths = (
        settings.resolved_managed_root,
        settings.resolved_staging_root,
        settings.resolved_export_root,
        settings.resolved_runtime_root,
    )
    unavailable = [
        path.name
        for path in required_paths
        if not path.is_dir() or not os.access(path, os.R_OK | os.W_OK)
    ]
    if unavailable:
        return ServiceCheck(
            status="error",
            detail=f"required storage unavailable: {', '.join(unavailable)}",
        )
    return ServiceCheck(status="ok")
