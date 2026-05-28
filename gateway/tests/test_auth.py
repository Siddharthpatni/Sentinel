"""Tests for auth signup/login + scoped API key CRUD."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import hash_api_key, resolve_project_by_key
from app.db.models import ApiKey, Base, Project
from app.main import app


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
    for mod in (
        "app.db.session",
        "app.routes.auth",
        "app.routes.api_keys",
        "app.routes.openai_compat",
        "app.routes.anthropic_compat",
        "app.routes.traces",
    ):
        monkeypatch.setattr(f"{mod}.AsyncSessionLocal", factory, raising=False)
    return factory


@pytest.fixture
async def client():  # type: ignore[no-untyped-def]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def project(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        p = Project(name=f"p-{uuid.uuid4()}", api_key=f"legacy-{uuid.uuid4()}")
        session.add(p)
        await session.commit()
        await session.refresh(p)
        return p


@pytest.mark.asyncio
async def test_signup_creates_user_org_and_session(client, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": "hunter22long", "display_name": "Test"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == email
    assert len(body["orgs"]) == 1
    assert body["orgs"][0]["role"] == "admin"
    assert "sentinel_session" in resp.cookies


@pytest.mark.asyncio
async def test_signup_duplicate_email_rejected(client, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/auth/signup", json={"email": email, "password": "hunter22long"})
    resp = await client.post("/api/auth/signup", json={"email": email, "password": "hunter22long"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    await client.post("/api/auth/signup", json={"email": email, "password": "hunter22long"})
    resp = await client.post("/api/auth/login", json={"email": email, "password": "wrong-pass-1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_session(client, session_factory):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_orgs_after_login(client, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    signup = await client.post(
        "/api/auth/signup", json={"email": email, "password": "hunter22long"}
    )
    token = signup.cookies["sentinel_session"]
    resp = await client.get("/api/auth/me", cookies={"sentinel_session": token})
    assert resp.status_code == 200
    assert resp.json()["email"] == email


@pytest.mark.asyncio
async def test_api_key_create_returns_plaintext_once(client, project):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    signup = await client.post(
        "/api/auth/signup", json={"email": email, "password": "hunter22long"}
    )
    token = signup.cookies["sentinel_session"]
    resp = await client.post(
        f"/api/projects/{project.id}/keys",
        json={"label": "ci", "scope": "admin"},
        cookies={"sentinel_session": token},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["plaintext_key"].startswith("sk-sentinel-")
    assert body["key_prefix"] == body["plaintext_key"][:12]

    # Subsequent list never includes plaintext
    listed = await client.get(
        f"/api/projects/{project.id}/keys", cookies={"sentinel_session": token}
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert "plaintext_key" not in rows[0]


@pytest.mark.asyncio
async def test_resolve_project_by_key_accepts_new_and_legacy(client, project, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    signup = await client.post(
        "/api/auth/signup", json={"email": email, "password": "hunter22long"}
    )
    token = signup.cookies["sentinel_session"]
    created = await client.post(
        f"/api/projects/{project.id}/keys",
        json={"label": "ci"},
        cookies={"sentinel_session": token},
    )
    plaintext = created.json()["plaintext_key"]

    async with session_factory() as session:
        # New scoped key resolves
        p1 = await resolve_project_by_key(session, plaintext)
        assert p1 is not None and p1.id == project.id
        # Legacy column still resolves
        p2 = await resolve_project_by_key(session, project.api_key)
        assert p2 is not None and p2.id == project.id
        # Unknown key returns None
        p3 = await resolve_project_by_key(session, "sk-sentinel-does-not-exist")
        assert p3 is None


@pytest.mark.asyncio
async def test_revoke_key_disables_resolution(client, project, session_factory):
    email = f"u{uuid.uuid4().hex[:8]}@example.com"
    signup = await client.post(
        "/api/auth/signup", json={"email": email, "password": "hunter22long"}
    )
    token = signup.cookies["sentinel_session"]
    created = await client.post(
        f"/api/projects/{project.id}/keys",
        json={"label": "ci"},
        cookies={"sentinel_session": token},
    )
    plaintext = created.json()["plaintext_key"]
    key_id = created.json()["id"]

    revoke = await client.delete(
        f"/api/projects/{project.id}/keys/{key_id}",
        cookies={"sentinel_session": token},
    )
    assert revoke.status_code == 204

    async with session_factory() as session:
        resolved = await resolve_project_by_key(session, plaintext)
        assert resolved is None
        # Hash still on row, just inactive
        row = await session.get(ApiKey, uuid.UUID(key_id))
        assert row is not None
        assert row.is_active is False
        assert row.key_hash == hash_api_key(plaintext)
