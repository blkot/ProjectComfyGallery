from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from comfy_gallery_api.dependencies import (
    CsrfPrincipalDep,
    DbSessionDep,
    PrincipalDep,
    SettingsDep,
)
from comfy_gallery_api.errors import ApiError
from comfy_gallery_api.rate_limit import LoginRateLimiter
from comfy_gallery_api.schemas import (
    ApiTokenCreatedResponse,
    ApiTokenCreateRequest,
    ApiTokenResponse,
    LoginRequest,
    SessionResponse,
    UserResponse,
)
from comfy_gallery_core.auth import (
    authenticate_user,
    create_api_token,
    create_web_session,
    delete_web_session,
    list_api_tokens,
    revoke_api_token,
)

auth_router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
token_router = APIRouter(prefix="/api/v1/api-tokens", tags=["api-tokens"])
_login_limiter: LoginRateLimiter | None = None


def _limiter(settings: SettingsDep) -> LoginRateLimiter:
    global _login_limiter
    if _login_limiter is None:
        _login_limiter = LoginRateLimiter(
            limit=settings.login_attempt_limit,
            window_seconds=settings.login_attempt_window_seconds,
        )
    return _login_limiter


def _client_key(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For", "").split(",", maxsplit=1)[0].strip()
    if forwarded:
        return forwarded
    return request.client.host if request.client is not None else "unknown"


@auth_router.post("/login", response_model=SessionResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DbSessionDep,
    settings: SettingsDep,
) -> SessionResponse:
    client_key = _client_key(request)
    limiter = _limiter(settings)
    if await limiter.is_blocked(client_key):
        raise ApiError(
            status_code=429,
            code="AUTH_RATE_LIMITED",
            message="Too many unsuccessful login attempts. Try again later.",
        )
    user = await authenticate_user(
        session,
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        await limiter.record_failure(client_key)
        raise ApiError(
            status_code=401,
            code="AUTH_INVALID_CREDENTIALS",
            message="The username or password is incorrect.",
        )
    await limiter.clear(client_key)

    created = await create_web_session(
        session,
        user=user,
        ttl_hours=settings.session_ttl_hours,
    )
    max_age = settings.session_ttl_hours * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        created.material.session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        created.material.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return SessionResponse(user=UserResponse.model_validate(user))


@auth_router.get("/session", response_model=SessionResponse)
async def get_session(principal: PrincipalDep) -> SessionResponse:
    return SessionResponse(user=UserResponse.model_validate(principal.user))


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
    settings: SettingsDep,
) -> Response:
    if principal.web_session is not None:
        await delete_web_session(session, record=principal.web_session)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(settings.csrf_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@token_router.get("", response_model=list[ApiTokenResponse])
async def get_tokens(
    principal: PrincipalDep,
    session: DbSessionDep,
) -> list[ApiTokenResponse]:
    records = await list_api_tokens(session, user_id=principal.user.id)
    return [ApiTokenResponse.model_validate(record) for record in records]


@token_router.post("", response_model=ApiTokenCreatedResponse, status_code=201)
async def add_token(
    payload: ApiTokenCreateRequest,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> ApiTokenCreatedResponse:
    created = await create_api_token(
        session,
        user=principal.user,
        label=payload.label,
    )
    return ApiTokenCreatedResponse(
        **ApiTokenResponse.model_validate(created.record).model_dump(),
        token=created.material.token,
    )


@token_router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_token(
    token_id: UUID,
    principal: CsrfPrincipalDep,
    session: DbSessionDep,
) -> Response:
    revoked = await revoke_api_token(
        session,
        token_id=token_id,
        user_id=principal.user.id,
    )
    if not revoked:
        raise ApiError(
            status_code=404,
            code="API_TOKEN_NOT_FOUND",
            message="The API token was not found.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
