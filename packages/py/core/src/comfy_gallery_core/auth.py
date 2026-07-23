from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from comfy_gallery_core.db.models import ApiToken, User, WebSession
from comfy_gallery_core.security import (
    ApiTokenMaterial,
    SessionMaterial,
    generate_api_token,
    generate_session_material,
    hash_password,
    hash_token,
    verify_password,
)


def normalize_username(username: str) -> str:
    return username.strip().casefold()


async def create_admin_if_missing(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> tuple[User, bool]:
    normalized = normalize_username(username)
    existing = await session.scalar(select(User).where(User.username_normalized == normalized))
    if existing is not None:
        return existing, False

    if len(password) < 12:
        raise ValueError("administrator password must contain at least 12 characters")

    user = User(
        username=username.strip(),
        username_normalized=normalized,
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, True


async def authenticate_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
) -> User | None:
    user = await session.scalar(
        select(User).where(User.username_normalized == normalize_username(username))
    )
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


@dataclass(frozen=True, slots=True)
class CreatedWebSession:
    record: WebSession
    material: SessionMaterial


async def create_web_session(
    session: AsyncSession,
    *,
    user: User,
    ttl_hours: int,
) -> CreatedWebSession:
    material = generate_session_material()
    record = WebSession(
        user_id=user.id,
        token_hash=material.session_token_hash,
        csrf_token_hash=material.csrf_token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return CreatedWebSession(record=record, material=material)


async def get_web_session(
    session: AsyncSession,
    *,
    token: str,
) -> tuple[WebSession, User] | None:
    result = await session.execute(
        select(WebSession, User)
        .join(User, User.id == WebSession.user_id)
        .where(
            WebSession.token_hash == hash_token(token),
            WebSession.expires_at > datetime.now(UTC),
            User.is_active.is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    record, user = row
    record.last_seen_at = datetime.now(UTC)
    await session.commit()
    return record, user


async def delete_web_session(session: AsyncSession, *, record: WebSession) -> None:
    await session.delete(record)
    await session.commit()


async def verify_csrf(record: WebSession, token: str | None) -> bool:
    return token is not None and hash_token(token) == record.csrf_token_hash


@dataclass(frozen=True, slots=True)
class CreatedApiToken:
    record: ApiToken
    material: ApiTokenMaterial


async def create_api_token(
    session: AsyncSession,
    *,
    user: User,
    label: str,
) -> CreatedApiToken:
    normalized_label = label.strip()
    if not normalized_label:
        raise ValueError("API token label cannot be empty")
    material = generate_api_token()
    record = ApiToken(
        user_id=user.id,
        label=normalized_label,
        token_prefix=material.prefix,
        token_hash=material.token_hash,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return CreatedApiToken(record=record, material=material)


async def get_api_token_user(
    session: AsyncSession,
    *,
    token: str,
) -> tuple[ApiToken, User] | None:
    result = await session.execute(
        select(ApiToken, User)
        .join(User, User.id == ApiToken.user_id)
        .where(
            ApiToken.token_hash == hash_token(token),
            ApiToken.revoked_at.is_(None),
            User.is_active.is_(True),
        )
    )
    row = result.one_or_none()
    if row is None:
        return None
    record, user = row
    record.last_used_at = datetime.now(UTC)
    await session.commit()
    return record, user


async def list_api_tokens(session: AsyncSession, *, user_id: UUID) -> list[ApiToken]:
    result = await session.scalars(
        select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.created_at.desc())
    )
    return list(result)


async def revoke_api_token(
    session: AsyncSession,
    *,
    token_id: UUID,
    user_id: UUID,
) -> bool:
    record = await session.scalar(
        select(ApiToken).where(ApiToken.id == token_id, ApiToken.user_id == user_id)
    )
    if record is None:
        return False
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await session.commit()
    return True
