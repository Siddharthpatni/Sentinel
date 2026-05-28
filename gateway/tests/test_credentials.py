"""Tests for /api/credentials CRUD routes."""

from __future__ import annotations

import uuid

import pytest
import respx
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Project, ProviderCredential
from app.main import app
from app.security.keyvault import decrypt


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
    for mod in ("app.db.session", "app.routes.credentials"):
        monkeypatch.setattr(f"{mod}.AsyncSessionLocal", factory)
    return factory


@pytest.fixture
async def project(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        p = Project(name=f"t-{uuid.uuid4()}", api_key=f"k-{uuid.uuid4()}")
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_create_credential_stores_ciphertext_not_plaintext(client, session_factory, project):
    plaintext = "sk-proj-secretLIVE123456789ABCDEF1234"
    resp = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "openai",
        "label": "primary",
        "api_key": plaintext,
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key_fingerprint"] == "sk-p…1234"
    assert "api_key" not in body
    assert plaintext not in resp.text

    async with session_factory() as session:
        cred = await session.get(ProviderCredential, uuid.UUID(body["id"]))
        assert cred is not None
        assert plaintext.encode() not in cred.encrypted_key
        assert decrypt(cred.encrypted_key) == plaintext


@pytest.mark.asyncio
async def test_create_rejects_unknown_provider(client, session_factory, project):
    resp = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "bogus",
        "label": "x",
        "api_key": "sk-test-12345678",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_rejects_unknown_project(client, session_factory):
    resp = await client.post("/api/credentials", json={
        "project_id": str(uuid.uuid4()),
        "provider": "openai",
        "label": "x",
        "api_key": "sk-test-12345678",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_label_returns_409(client, session_factory, project):
    payload = {
        "project_id": str(project.id),
        "provider": "openai",
        "label": "primary",
        "api_key": "sk-test-12345678",
    }
    await client.post("/api/credentials", json=payload)
    resp = await client.post("/api/credentials", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_filters_by_project_and_provider(client, project, session_factory):
    async with session_factory() as session:
        other = Project(name=f"other-{uuid.uuid4()}", api_key=f"k-{uuid.uuid4()}")
        session.add(other)
        await session.commit()
        await session.refresh(other)

    for prov in ("openai", "anthropic"):
        await client.post("/api/credentials", json={
            "project_id": str(project.id),
            "provider": prov,
            "label": "p",
            "api_key": "sk-test-12345678",
        })
    await client.post("/api/credentials", json={
        "project_id": str(other.id),
        "provider": "openai",
        "label": "p",
        "api_key": "sk-test-12345678",
    })

    resp = await client.get(f"/api/credentials?project_id={project.id}")
    assert resp.json()["total"] == 2

    resp = await client.get(f"/api/credentials?project_id={project.id}&provider=openai")
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_patch_toggles_active(client, session_factory, project):
    create = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "openai",
        "label": "p",
        "api_key": "sk-test-12345678",
    })
    cid = create.json()["id"]
    resp = await client.patch(f"/api/credentials/{cid}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_removes_credential(client, project, session_factory):
    create = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "openai",
        "label": "p",
        "api_key": "sk-test-12345678",
    })
    cid = create.json()["id"]
    resp = await client.delete(f"/api/credentials/{cid}")
    assert resp.status_code == 204

    async with session_factory() as session:
        assert await session.get(ProviderCredential, uuid.UUID(cid)) is None


@pytest.mark.asyncio
@respx.mock
async def test_credential_test_endpoint_returns_ok_on_2xx(client, session_factory, project):
    create = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "openai",
        "label": "p",
        "api_key": "sk-live-key-1234567890",
    })
    cid = create.json()["id"]

    respx.get("https://api.openai.com/v1/models").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    resp = await client.post(f"/api/credentials/{cid}/test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status_code"] == 200


@pytest.mark.asyncio
@respx.mock
async def test_credential_test_endpoint_reports_401(client, session_factory, project):
    create = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "anthropic",
        "label": "p",
        "api_key": "sk-ant-bad-key-1234567890",
    })
    cid = create.json()["id"]

    respx.get("https://api.anthropic.com/v1/models").mock(
        return_value=httpx.Response(
            401, json={"error": {"message": "invalid x-api-key"}}
        )
    )
    resp = await client.post(f"/api/credentials/{cid}/test")
    body = resp.json()
    assert body["ok"] is False
    assert body["status_code"] == 401
    assert "invalid" in body["message"].lower()


@pytest.mark.asyncio
async def test_credential_test_returns_404_for_unknown(client, session_factory):
    resp = await client.post(f"/api/credentials/{uuid.uuid4()}/test")
    assert resp.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_credential_test_handles_network_error(client, session_factory, project):
    create = await client.post("/api/credentials", json={
        "project_id": str(project.id),
        "provider": "openrouter",
        "label": "p",
        "api_key": "sk-or-1234567890",
    })
    cid = create.json()["id"]

    respx.get("https://openrouter.ai/api/v1/models").mock(
        side_effect=httpx.ConnectError("DNS failure")
    )
    resp = await client.post(f"/api/credentials/{cid}/test")
    body = resp.json()
    assert body["ok"] is False
    assert body["status_code"] == 0
    assert "network" in body["message"].lower()
