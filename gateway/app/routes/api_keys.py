"""Scoped API keys for a project.

The plaintext token is returned exactly once at creation; subsequent
listings only show the short prefix and the bcrypt-style fingerprint.
Revocation soft-deletes the row (``is_active = false``) so historical
``last_used_at`` provenance is preserved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import generate_api_key, get_current_user
from app.db.models import ApiKey, OrgMember, Project, User
from app.db.session import get_async_session

router = APIRouter(prefix="/api/projects/{project_id}/keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    scope: str = Field(default="admin", pattern=r"^(admin|ingest)$")


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    label: str
    key_prefix: str
    scope: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}


class ApiKeyCreatedResponse(ApiKeyResponse):
    plaintext_key: str


async def _require_project_access(
    session: AsyncSession, project_id: uuid.UUID, user: User
) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if project.org_id is not None:
        result = await session.execute(
            select(OrgMember).where(
                OrgMember.org_id == project.org_id,
                OrgMember.user_id == user.id,
            )
        )
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="not a member of this project's org")
    return project


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    project_id: uuid.UUID,
    payload: ApiKeyCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> ApiKeyCreatedResponse:
    await _require_project_access(session, project_id, user)
    raw, digest, prefix = generate_api_key()
    row = ApiKey(
        project_id=project_id,
        created_by_user_id=user.id,
        label=payload.label,
        key_hash=digest,
        key_prefix=prefix,
        scope=payload.scope,
    )
    session.add(row)
    try:
        await session.flush()
    except Exception as exc:  # unique constraint on (project_id, label)
        raise HTTPException(status_code=409, detail="label already exists in this project") from exc
    return ApiKeyCreatedResponse(
        id=row.id,
        label=row.label,
        key_prefix=row.key_prefix,
        scope=row.scope,
        is_active=row.is_active,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        plaintext_key=raw,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[ApiKey]:
    await _require_project_access(session, project_id, user)
    result = await session.execute(
        select(ApiKey).where(ApiKey.project_id == project_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    project_id: uuid.UUID,
    key_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> None:
    await _require_project_access(session, project_id, user)
    row = await session.get(ApiKey, key_id)
    if row is None or row.project_id != project_id:
        raise HTTPException(status_code=404, detail="key not found")
    row.is_active = False
    row.revoked_at = datetime.now(UTC)
