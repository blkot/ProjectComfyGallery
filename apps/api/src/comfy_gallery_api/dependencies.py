from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_api.errors import ApiError
from comfy_gallery_core.auth import get_api_token_user, get_web_session, verify_csrf
from comfy_gallery_core.config import Settings, get_settings
from comfy_gallery_core.db import get_database
from comfy_gallery_core.db.models import ApiToken, User, WebSession


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with get_database().session() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@dataclass(frozen=True, slots=True)
class Principal:
    user: User
    auth_kind: Literal["session", "api_token"]
    web_session: WebSession | None = None
    api_token: ApiToken | None = None


async def require_principal(
    request: Request,
    session: DbSessionDep,
    settings: SettingsDep,
) -> Principal:
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        raw_token = authorization.removeprefix("Bearer ").strip()
        if raw_token:
            resolved = await get_api_token_user(session, token=raw_token)
            if resolved is not None:
                token, user = resolved
                return Principal(user=user, auth_kind="api_token", api_token=token)

    session_token = request.cookies.get(settings.session_cookie_name)
    if session_token:
        resolved_session = await get_web_session(session, token=session_token)
        if resolved_session is not None:
            web_session, user = resolved_session
            return Principal(user=user, auth_kind="session", web_session=web_session)

    raise ApiError(
        status_code=401,
        code="AUTH_REQUIRED",
        message="Authentication is required.",
    )


PrincipalDep = Annotated[Principal, Depends(require_principal)]


async def require_csrf(request: Request, principal: PrincipalDep) -> Principal:
    if principal.auth_kind == "api_token":
        return principal
    if principal.web_session is None:
        raise ApiError(
            status_code=401,
            code="AUTH_REQUIRED",
            message="Authentication is required.",
        )
    csrf_token = request.headers.get("X-CSRF-Token")
    if not await verify_csrf(principal.web_session, csrf_token):
        raise ApiError(
            status_code=403,
            code="CSRF_INVALID",
            message="The CSRF token is missing or invalid.",
        )
    return principal


CsrfPrincipalDep = Annotated[Principal, Depends(require_csrf)]
