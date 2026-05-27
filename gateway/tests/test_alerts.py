"""Tests for the alerts evaluator + routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.alerts.evaluator import evaluate_metric, is_triggered
from app.db.models import Base, Project, Trace
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
    # Patch the factory in every route module that captures it.
    for mod in (
        "app.db.session",
        "app.routes.alerts",
        "app.routes.annotations",
    ):
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
async def traces_in_window(session_factory, project):  # type: ignore[no-untyped-def]
    now = datetime.now(UTC)
    async with session_factory() as session:
        for i in range(10):
            session.add(
                Trace(
                    project_id=project.id,
                    provider="openai",
                    model="gpt-4o-mini",
                    latency_ms=100 + i * 100,
                    prompt_tokens=10,
                    completion_tokens=5,
                    cost_usd=0.01,
                    status_code=500 if i < 2 else 200,
                    created_at=now - timedelta(minutes=i),
                )
            )
        await session.commit()


def test_is_triggered_gt():
    assert is_triggered(10.0, "gt", 5.0) is True
    assert is_triggered(3.0, "gt", 5.0) is False


def test_is_triggered_lt():
    assert is_triggered(3.0, "lt", 5.0) is True
    assert is_triggered(10.0, "lt", 5.0) is False


async def test_evaluate_cost_per_hour(session_factory, project, traces_in_window):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        value = await evaluate_metric(
            session,
            project_id=project.id,
            metric="cost_per_hour_usd",
            window_minutes=60,
        )
    # 10 traces × $0.01 = $0.10 over 60min → 0.10/hour
    assert value == pytest.approx(0.10, rel=0.01)


async def test_evaluate_error_rate(session_factory, project, traces_in_window):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        value = await evaluate_metric(
            session,
            project_id=project.id,
            metric="error_rate_pct",
            window_minutes=60,
        )
    # 2 errors out of 10 = 20%
    assert value == pytest.approx(20.0, rel=0.01)


async def test_create_and_check_alert(session_factory, project, traces_in_window):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create = await client.post(
            "/api/alerts",
            json={
                "project_id": str(project.id),
                "name": "burn",
                "metric": "cost_per_hour_usd",
                "comparator": "gt",
                "threshold": 0.05,
                "window_minutes": 60,
            },
        )
        assert create.status_code == 201, create.text
        alert_id = create.json()["id"]

        check = await client.post(f"/api/alerts/{alert_id}/check")
        assert check.status_code == 200, check.text
        body = check.json()
        assert body["triggered"] is True
        assert body["value"] > 0.05


async def test_alert_validation(session_factory, project):  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        bad = await client.post(
            "/api/alerts",
            json={
                "project_id": str(project.id),
                "name": "x",
                "metric": "not_a_metric",
                "comparator": "gt",
                "threshold": 1,
                "window_minutes": 60,
            },
        )
        assert bad.status_code == 400
