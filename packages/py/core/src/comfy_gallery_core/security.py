import hashlib
import secrets
from dataclasses import dataclass

from pwdlib import PasswordHash

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token(*, prefix: str = "", entropy_bytes: int = 32) -> str:
    return f"{prefix}{secrets.token_urlsafe(entropy_bytes)}"


@dataclass(frozen=True, slots=True)
class SessionMaterial:
    session_token: str
    session_token_hash: str
    csrf_token: str
    csrf_token_hash: str


def generate_session_material() -> SessionMaterial:
    session_token = generate_token(entropy_bytes=32)
    csrf_token = generate_token(entropy_bytes=24)
    return SessionMaterial(
        session_token=session_token,
        session_token_hash=hash_token(session_token),
        csrf_token=csrf_token,
        csrf_token_hash=hash_token(csrf_token),
    )


@dataclass(frozen=True, slots=True)
class ApiTokenMaterial:
    token: str
    token_hash: str
    prefix: str


def generate_api_token() -> ApiTokenMaterial:
    token = generate_token(prefix="cgpat_", entropy_bytes=32)
    return ApiTokenMaterial(
        token=token,
        token_hash=hash_token(token),
        prefix=token[:13],
    )
