"""Tests for keyvault.get_provider_key — resolution order + 402 on miss."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Project, ProviderCredential
from app.security.keyvault import encrypt, fingerprint, get_provider_key


@pytest.fixture
async def session_factory(monkeypatch):  # type: ignore[no-untyped-def]
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.security.keyvault.AsyncSessionLocal", factory, raising=False)
    # keyvault imports lazily, so patch via the source module too:
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", factory)
    return factory


@pytest.fixture
async def project(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        p = Project(name=f"t-{uuid.uuid4()}", api_key=f"k-{uuid.uuid4()}")
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


@pytest.mark.asyncio
async def test_returns_decrypted_key_when_credential_exists(session_factory, project):
    plaintext = "sk-proj-abcdef1234567890ABCDEF1234567890"
    async with session_factory() as session:
        session.add(ProviderCredential(
            project_id=project.id,
            provider="openai",
            encrypted_key=encrypt(plaintext),
            key_fingerprint=fingerprint(plaintext),
            label="default",
        ))
        await session.commit()

    # Patch the lazy import inside get_provider_key
    import app.db.session as db_session
    from app.security import keyvault
    keyvault.AsyncSessionLocal = db_session.AsyncSessionLocal  # type: ignore[attr-defined]

    result = await get_provider_key(project.id, "openai")
    assert result == plaintext


@pytest.mark.asyncio
async def test_raises_402_when_no_credential_and_no_env(session_factory, project, monkeypatch):
    monkeypatch.setattr("app.config.settings.openai_api_key", "")
    monkeypatch.setattr("app.config.settings.anthropic_api_key", "")
    monkeypatch.setattr("app.config.settings.openrouter_api_key", "")

    with pytest.raises(HTTPException) as exc:
        await get_provider_key(project.id, "openai")
    assert exc.value.status_code == 402
    assert "openai" in exc.value.detail


@pytest.mark.asyncio
async def test_env_fallback_when_no_credential(session_factory, project, monkeypatch):
    monkeypatch.setattr("app.config.settings.openai_api_key", "sk-env-fallback")
    result = await get_provider_key(project.id, "openai")
    assert result == "sk-env-fallback"


@pytest.mark.asyncio
async def test_inactive_credential_is_skipped(session_factory, project, monkeypatch):
    monkeypatch.setattr("app.config.settings.openai_api_key", "")
    plaintext = "sk-proj-inactiveKEY1234567890ABCDEF12"
    async with session_factory() as session:
        session.add(ProviderCredential(
            project_id=project.id,
            provider="openai",
            encrypted_key=encrypt(plaintext),
            key_fingerprint=fingerprint(plaintext),
            label="off",
            is_active=False,
        ))
        await session.commit()

    with pytest.raises(HTTPException) as exc:
        await get_provider_key(project.id, "openai")
    assert exc.value.status_code == 402
