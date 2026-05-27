"""Tests for trace annotations + session resolution."""

from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base, Project, Trace
from app.main import app
from app.routes.annotations import resolve_session_id


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
    for mod in ("app.db.session", "app.routes.annotations"):
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
async def trace(session_factory, project):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        t = Trace(
            project_id=project.id,
            provider="openai",
            model="gpt-4o-mini",
            latency_ms=120,
            prompt_tokens=10,
            completion_tokens=5,
            cost_usd=0.001,
            status_code=200,
        )
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return t


async def test_create_annotation(session_factory, trace):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/annotations",
            json={
                "trace_id": str(trace.id),
                "rating": "thumbs_up",
                "comment": "Nailed it.",
                "author": "alice",
            },
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["rating"] == "thumbs_up"

        listed = await client.get(f"/api/annotations?trace_id={trace.id}")
        assert listed.status_code == 200
        assert listed.json()["total"] == 1


async def test_annotation_invalid_rating(session_factory, trace):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/annotations",
            json={
                "trace_id": str(trace.id),
                "rating": "five_stars",
            },
        )
        assert resp.status_code == 400


async def test_resolve_session_creates_and_reuses(session_factory, project):  # type: ignore[no-untyped-def]
    body = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "hi"}],
        "_sentinel": {"session_id": "user-123", "session_name": "Alice's chat"},
    }
    first = await resolve_session_id(project.id, body)
    assert first is not None

    # Same external_id → same internal session row
    second = await resolve_session_id(project.id, body)
    assert second == first


async def test_resolve_session_no_tag_returns_none(session_factory, project):  # type: ignore[no-untyped-def]
    body = {"model": "gpt-4o-mini", "messages": []}
    sid = await resolve_session_id(project.id, body)
    assert sid is None


async def test_session_listing_and_get(session_factory, project, trace):  # type: ignore[no-untyped-def]
    body = {"_sentinel": {"session_id": "thread-42"}}
    sid = await resolve_session_id(project.id, body)
    assert sid is not None

    async with session_factory() as s:
        t = await s.get(Trace, trace.id)
        t.session_id = sid
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        listed = await client.get(f"/api/sessions?project_id={project.id}")
        assert listed.status_code == 200, listed.text
        items = listed.json()["sessions"]
        assert any(item["external_id"] == "thread-42" for item in items)
        target = next(item for item in items if item["external_id"] == "thread-42")
        assert target["trace_count"] == 1

        detail = await client.get(f"/api/sessions/{sid}")
        assert detail.status_code == 200
        assert str(trace.id) in detail.json()["trace_ids"]
