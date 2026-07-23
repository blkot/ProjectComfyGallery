from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from comfy_gallery_core.auth import (
    authenticate_user,
    create_admin_if_missing,
    create_api_token,
    create_web_session,
    get_api_token_user,
    get_web_session,
    revoke_api_token,
    verify_csrf,
)
from comfy_gallery_core.db.base import Base


async def test_authentication_records_round_trip() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        assert isinstance(session, AsyncSession)
        user, created = await create_admin_if_missing(
            session,
            username="Admin",
            password="correct horse battery staple",
        )
        assert created

        same_user, created_again = await create_admin_if_missing(
            session,
            username="admin",
            password="a different valid password",
        )
        assert not created_again
        assert same_user.id == user.id

        authenticated = await authenticate_user(
            session,
            username=" ADMIN ",
            password="correct horse battery staple",
        )
        assert authenticated is not None
        assert authenticated.id == user.id

        created_session = await create_web_session(session, user=user, ttl_hours=24)
        resolved_session = await get_web_session(
            session,
            token=created_session.material.session_token,
        )
        assert resolved_session is not None
        web_session, session_user = resolved_session
        assert session_user.id == user.id
        assert await verify_csrf(web_session, created_session.material.csrf_token)
        assert not await verify_csrf(web_session, "wrong")

        created_token = await create_api_token(session, user=user, label="ComfyUI")
        resolved_token = await get_api_token_user(
            session,
            token=created_token.material.token,
        )
        assert resolved_token is not None
        token_record, token_user = resolved_token
        assert token_user.id == user.id
        assert token_record.last_used_at is not None

        assert await revoke_api_token(
            session,
            token_id=created_token.record.id,
            user_id=user.id,
        )
        assert await get_api_token_user(session, token=created_token.material.token) is None

    await engine.dispose()
