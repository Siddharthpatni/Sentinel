"""Authentication primitives: password hashing, JWT, request dependencies.

Two auth surfaces coexist:

* Dashboard users authenticate with email + password, receive a signed JWT
  in an httpOnly cookie, and are resolved on each request via
  :func:`get_current_user`.
* SDKs and direct API consumers send a project-scoped API key (raw token
  passed as ``Authorization: Bearer`` or ``x-sentinel-key``). The token is
  SHA-256 hashed and looked up against :class:`ApiKey`. Legacy
  ``Project.api_key`` strings are still accepted for backward compat.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import ApiKey, Project, User
from app.db.session import get_async_session

API_KEY_PREFIX = "sk-sentinel-"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def issue_session_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.sentinel_jwt_ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.sentinel_jwt_secret, algorithm="HS256")


def decode_session_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(token, settings.sentinel_jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    try:
        return uuid.UUID(sub)
    except (ValueError, TypeError):
        return None


def generate_api_key() -> tuple[str, str, str]:
    """Return ``(plaintext, sha256_hash, display_prefix)`` for a new key."""
    raw = API_KEY_PREFIX + secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, digest, raw[:12]


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_current_user(
    session: AsyncSession = Depends(get_async_session),
    cookie_token: str | None = Cookie(default=None, alias=settings.sentinel_cookie_name),
    authorization: str | None = Header(default=None),
) -> User:
    """Resolve the logged-in dashboard user.

    Looks for a JWT in the session cookie first, then in a
    ``Authorization: Bearer`` header (for tests / non-browser clients).
    Raises 401 if no valid token is present.
    """
    token = cookie_token
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    user_id = decode_session_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid session")
    user = await session.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    return user


async def resolve_project_by_key(session: AsyncSession, raw_key: str) -> Project | None:
    """Resolve a project from a raw API key.

    Checks the modern :class:`ApiKey` table first (SHA-256 hash lookup),
    then falls back to the legacy ``Project.api_key`` column so existing
    deployments keep working.
    """
    if not raw_key:
        return None
    digest = hash_api_key(raw_key)
    result = await session.execute(
        select(ApiKey).where(ApiKey.key_hash == digest, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if api_key is not None:
        api_key.last_used_at = datetime.now(UTC)
        project = await session.get(Project, api_key.project_id)
        if project is not None:
            return project
    legacy = await session.execute(select(Project).where(Project.api_key == raw_key))
    return legacy.scalar_one_or_none()
