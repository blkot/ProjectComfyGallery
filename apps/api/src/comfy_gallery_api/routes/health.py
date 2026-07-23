import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from comfy_gallery_api import __version__
from comfy_gallery_api.dependencies import DbSessionDep, SettingsDep
from comfy_gallery_api.schemas import HealthResponse
from comfy_gallery_api.services import check_database, check_redis, check_storage

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="comfy-gallery-api",
        version=__version__,
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def readiness(
    session: DbSessionDep,
    settings: SettingsDep,
) -> HealthResponse | JSONResponse:
    database_check, redis_check, storage_check = await asyncio.gather(
        check_database(session),
        check_redis(settings.redis_url),
        asyncio.to_thread(check_storage, settings),
    )
    checks = {
        "database": database_check,
        "redis": redis_check,
        "storage": storage_check,
    }
    healthy = all(check.status == "ok" for check in checks.values())
    response = HealthResponse(
        status="ok" if healthy else "degraded",
        service="comfy-gallery-api",
        version=__version__,
        checks=checks,
    )
    if healthy:
        return response
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
