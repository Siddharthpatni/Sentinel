"""Authentication routes: signup, login, logout, /me.

Signup creates a User and a personal Org and an admin OrgMember row in a
single transaction. Login verifies the password, issues a JWT, and sets
it as an httpOnly cookie scoped to the gateway origin.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    get_current_user,
    hash_password,
    issue_session_token,
    verify_password,
)
from app.config import settings
from app.db.models import Org, OrgMember, User
from app.db.seed import backfill_owner_membership
from app.db.session import get_async_session

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(email: str) -> str:
    base = _SLUG_RE.sub("-", email.split("@", 1)[0].lower()).strip("-") or "org"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    orgs: list[dict]

    model_config = {"from_attributes": True}


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.sentinel_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=settings.sentinel_jwt_ttl_seconds,
        path="/",
    )


async def _user_with_orgs(session: AsyncSession, user: User) -> dict:
    rows = await session.execute(
        select(Org, OrgMember.role)
        .join(OrgMember, OrgMember.org_id == Org.id)
        .where(OrgMember.user_id == user.id)
        .order_by(Org.created_at)
    )
    orgs = [
        {"id": str(org.id), "name": org.name, "slug": org.slug, "role": role}
        for org, role in rows.all()
    ]
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "orgs": orgs,
    }


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="email already registered")

    user = User(
        email=str(payload.email),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        last_login_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()

    org = Org(name=payload.display_name or str(payload.email), slug=_slugify(str(payload.email)))
    session.add(org)
    await session.flush()

    session.add(OrgMember(org_id=org.id, user_id=user.id, role="admin"))
    await session.flush()

    # If this is the very first user, also adopt the default org as admin so
    # the legacy default project becomes manageable from the dashboard.
    user_count = (await session.execute(select(User))).scalars().all()
    if len(user_count) <= 1:
        await backfill_owner_membership(session, user)

    token = issue_session_token(user.id)
    _set_session_cookie(response, token)
    return await _user_with_orgs(session, user)


@router.post("/login", response_model=UserResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="account disabled")

    user.last_login_at = datetime.now(UTC)
    token = issue_session_token(user.id)
    _set_session_cookie(response, token)
    return await _user_with_orgs(session, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(settings.sentinel_cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserResponse)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> dict:
    return await _user_with_orgs(session, user)
