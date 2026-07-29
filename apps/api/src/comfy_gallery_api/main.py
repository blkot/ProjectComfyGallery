from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHttpException

from comfy_gallery_api import __version__
from comfy_gallery_api.errors import (
    ApiError,
    api_error_handler,
    http_error_handler,
    validation_error_handler,
)
from comfy_gallery_api.routes.analytics import router as analytics_router
from comfy_gallery_api.routes.auth import auth_router, token_router
from comfy_gallery_api.routes.evaluations import router as evaluations_router
from comfy_gallery_api.routes.exports import router as exports_router
from comfy_gallery_api.routes.health import router as health_router
from comfy_gallery_api.routes.imports import router as imports_router
from comfy_gallery_api.routes.jobs import router as jobs_router
from comfy_gallery_api.routes.media import router as media_router
from comfy_gallery_api.routes.registries import router as registries_router
from comfy_gallery_api.routes.system import router as system_router
from comfy_gallery_api.routes.variants import router as variants_router
from comfy_gallery_api.routes.workflows import router as workflows_router
from comfy_gallery_core.config import get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.logging import configure_logging
from comfy_gallery_core.media.files import ensure_storage_layout
from comfy_gallery_core.media.variants import reconcile_spatial_availability
from comfy_gallery_core.operations.recovery import reconcile_interrupted_jobs

settings = get_settings()
configure_logging(
    level=settings.log_level,
    json_logs=settings.environment != "development",
)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ensure_storage_layout(settings)
    async with get_database().session() as session:
        recovery = await reconcile_interrupted_jobs(session, settings=settings)
        reconciled_media = await reconcile_spatial_availability(session)
    if recovery.examined:
        logger.info(
            "startup_job_recovery",
            examined=recovery.examined,
            requeued=recovery.requeued,
            failed=recovery.failed,
        )
    if reconciled_media:
        logger.info("startup_spatial_availability_reconciled", media_count=reconciled_media)
    logger.info("api_starting", version=__version__, environment=settings.environment)
    yield
    await get_database().dispose()
    logger.info("api_stopped")


app = FastAPI(
    title="Project Comfy Gallery API",
    version=__version__,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "Idempotency-Key"],
)
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHttpException, http_error_handler)


@app.middleware("http")
async def request_context(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    try:
        response = await call_next(request)
    finally:
        structlog.contextvars.clear_contextvars()
    response.headers["X-Request-ID"] = request_id
    return response


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(token_router)
app.include_router(system_router)
app.include_router(imports_router)
app.include_router(jobs_router)
app.include_router(media_router)
app.include_router(variants_router)
app.include_router(workflows_router)
app.include_router(registries_router)
app.include_router(evaluations_router)
app.include_router(analytics_router)
app.include_router(exports_router)
