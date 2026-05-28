"""CRUD routes for project-scoped provider credentials (BYOK).

Plaintext API keys NEVER leave the gateway after creation — responses
only echo the ``key_fingerprint`` (first4…last4). Update operations
cannot read or rotate the key in-place; rotation = delete + create.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.db.models import Project, ProviderCredential
from app.db.session import AsyncSessionLocal
from app.security.keyvault import encrypt, fingerprint

router = APIRouter(prefix="/api/credentials", tags=["credentials"])

ALLOWED_PROVIDERS = {"openai", "anthropic", "openrouter", "gemini"}


class CredentialCreate(BaseModel):
    project_id: uuid.UUID
    provider: str = Field(..., min_length=1, max_length=32)
    label: str = Field(..., min_length=1, max_length=120)
    api_key: str = Field(..., min_length=8)


class CredentialUpdate(BaseModel):
    label: str | None = Field(None, min_length=1, max_length=120)
    is_active: bool | None = None


class CredentialResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    provider: str
    label: str
    key_fingerprint: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None

    model_config = {"from_attributes": True}


class CredentialListResponse(BaseModel):
    credentials: list[CredentialResponse]
    total: int


def _validate_provider(provider: str) -> None:
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown provider {provider!r}. Allowed: {sorted(ALLOWED_PROVIDERS)}",
        )


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(payload: CredentialCreate) -> CredentialResponse:
    _validate_provider(payload.provider)
    async with AsyncSessionLocal() as session:
        if await session.get(Project, payload.project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")

        cred = ProviderCredential(
            project_id=payload.project_id,
            provider=payload.provider,
            encrypted_key=encrypt(payload.api_key),
            key_fingerprint=fingerprint(payload.api_key),
            label=payload.label,
            is_active=True,
        )
        session.add(cred)
        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise HTTPException(
                status_code=409,
                detail=f"A credential with label {payload.label!r} already exists for this provider",
            ) from exc
        await session.refresh(cred)
        return CredentialResponse.model_validate(cred)


@router.get("", response_model=CredentialListResponse)
async def list_credentials(
    project_id: uuid.UUID | None = Query(None),
    provider: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> CredentialListResponse:
    async with AsyncSessionLocal() as session:
        query = select(ProviderCredential).order_by(ProviderCredential.created_at.desc())
        count_query = select(func.count()).select_from(ProviderCredential)

        if project_id is not None:
            query = query.where(ProviderCredential.project_id == project_id)
            count_query = count_query.where(ProviderCredential.project_id == project_id)
        if provider is not None:
            query = query.where(ProviderCredential.provider == provider)
            count_query = count_query.where(ProviderCredential.provider == provider)

        result = await session.execute(query.limit(limit))
        creds = result.scalars().all()
        total = (await session.execute(count_query)).scalar_one()

        return CredentialListResponse(
            credentials=[CredentialResponse.model_validate(c) for c in creds],
            total=total,
        )


@router.patch("/{credential_id}", response_model=CredentialResponse)
async def update_credential(
    credential_id: uuid.UUID, payload: CredentialUpdate
) -> CredentialResponse:
    async with AsyncSessionLocal() as session:
        cred = await session.get(ProviderCredential, credential_id)
        if cred is None:
            raise HTTPException(status_code=404, detail="Credential not found")
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(cred, k, v)
        await session.commit()
        await session.refresh(cred)
        return CredentialResponse.model_validate(cred)


@router.delete("/{credential_id}", status_code=204)
async def delete_credential(credential_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        cred = await session.get(ProviderCredential, credential_id)
        if cred is None:
            raise HTTPException(status_code=404, detail="Credential not found")
        await session.delete(cred)
        await session.commit()
