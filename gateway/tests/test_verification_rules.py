"""Integration tests for the verification rules CRUD route."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Project
from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.fixture
async def db_session(monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    """Provide an in-memory SQLite session and patch the route's session factory."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(
        "app.routes.verifications.AsyncSessionLocal", session_factory
    )
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", session_factory)

    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def project(db_session: AsyncSession) -> Project:
    p = Project(name="test-project", api_key="sk-test-001")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)
    return p


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_create_rule_happy_path(client: AsyncClient, project: Project) -> None:
    payload = {
        "project_id": str(project.id),
        "name": "refund-check",
        "match_jsonpath": "$.messages[?(@.role=='user')]",
        "sample_rate": 0.25,
        "judge_model": "claude-haiku-4-5",
        "judge_prompt_template": "Check: {{ request }} -> {{ response }}",
        "enabled": True,
    }
    res = await client.post("/api/verification-rules", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "refund-check"
    assert body["sample_rate"] == 0.25
    assert body["enabled"] is True


async def test_create_rule_unknown_project(client: AsyncClient) -> None:
    payload = {
        "project_id": str(uuid.uuid4()),
        "name": "x",
        "match_jsonpath": "$",
        "sample_rate": 0.1,
        "judge_model": "claude-haiku-4-5",
        "judge_prompt_template": "t",
    }
    res = await client.post("/api/verification-rules", json=payload)
    assert res.status_code == 404


async def test_create_rule_invalid_sample_rate(
    client: AsyncClient, project: Project
) -> None:
    payload = {
        "project_id": str(project.id),
        "name": "x",
        "match_jsonpath": "$",
        "sample_rate": 1.5,
        "judge_model": "claude-haiku-4-5",
        "judge_prompt_template": "t",
    }
    res = await client.post("/api/verification-rules", json=payload)
    assert res.status_code == 422


async def test_list_rules_filters(client: AsyncClient, project: Project) -> None:
    base = {
        "project_id": str(project.id),
        "match_jsonpath": "$",
        "sample_rate": 0.1,
        "judge_model": "claude-haiku-4-5",
        "judge_prompt_template": "t",
    }
    await client.post("/api/verification-rules", json={**base, "name": "a", "enabled": True})
    await client.post("/api/verification-rules", json={**base, "name": "b", "enabled": False})

    all_rules = (await client.get("/api/verification-rules")).json()
    assert all_rules["total"] == 2

    enabled_only = (
        await client.get("/api/verification-rules", params={"enabled": True})
    ).json()
    assert enabled_only["total"] == 1
    assert enabled_only["rules"][0]["name"] == "a"


async def test_patch_rule_toggles_enabled(client: AsyncClient, project: Project) -> None:
    create = await client.post(
        "/api/verification-rules",
        json={
            "project_id": str(project.id),
            "name": "toggle-me",
            "match_jsonpath": "$",
            "sample_rate": 0.1,
            "judge_model": "claude-haiku-4-5",
            "judge_prompt_template": "t",
            "enabled": True,
        },
    )
    rule_id = create.json()["id"]
    patched = await client.patch(
        f"/api/verification-rules/{rule_id}", json={"enabled": False}
    )
    assert patched.status_code == 200
    assert patched.json()["enabled"] is False


async def test_delete_rule(client: AsyncClient, project: Project) -> None:
    create = await client.post(
        "/api/verification-rules",
        json={
            "project_id": str(project.id),
            "name": "doomed",
            "match_jsonpath": "$",
            "sample_rate": 0.1,
            "judge_model": "claude-haiku-4-5",
            "judge_prompt_template": "t",
        },
    )
    rule_id = create.json()["id"]
    deleted = await client.delete(f"/api/verification-rules/{rule_id}")
    assert deleted.status_code == 204
    missing = await client.get(f"/api/verification-rules/{rule_id}")
    assert missing.status_code == 404
