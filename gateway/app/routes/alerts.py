"""Alerts routes: CRUD + on-demand /check."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.alerts.evaluator import (
    ALLOWED_COMPARATORS,
    ALLOWED_METRICS,
    evaluate_metric,
    is_triggered,
)
from app.db.models import Alert, Project
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    metric: str
    comparator: str = "gt"
    threshold: float
    window_minutes: int = Field(default=60, ge=1, le=10080)
    enabled: bool = True


class AlertUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    metric: str | None = None
    comparator: str | None = None
    threshold: float | None = None
    window_minutes: int | None = Field(default=None, ge=1, le=10080)
    enabled: bool | None = None


class AlertResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    metric: str
    comparator: str
    threshold: float
    window_minutes: int
    enabled: bool
    last_checked_at: datetime | None
    last_value: float | None
    last_triggered: bool

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    alerts: list[AlertResponse]
    total: int


class AlertCheckResponse(BaseModel):
    alert_id: uuid.UUID
    metric: str
    value: float
    threshold: float
    comparator: str
    triggered: bool
    checked_at: datetime


def _validate(metric: str | None, comparator: str | None) -> None:
    if metric is not None and metric not in ALLOWED_METRICS:
        raise HTTPException(400, f"metric must be one of {sorted(ALLOWED_METRICS)}")
    if comparator is not None and comparator not in ALLOWED_COMPARATORS:
        raise HTTPException(400, f"comparator must be one of {sorted(ALLOWED_COMPARATORS)}")


@router.post("", response_model=AlertResponse, status_code=201)
async def create_alert(payload: AlertCreate) -> AlertResponse:
    _validate(payload.metric, payload.comparator)
    async with AsyncSessionLocal() as session:
        if await session.get(Project, payload.project_id) is None:
            raise HTTPException(404, "Project not found")
        row = Alert(
            project_id=payload.project_id,
            name=payload.name,
            metric=payload.metric,
            comparator=payload.comparator,
            threshold=payload.threshold,
            window_minutes=payload.window_minutes,
            enabled=payload.enabled,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return AlertResponse.model_validate(row)


@router.get("", response_model=AlertListResponse)
async def list_alerts(
    project_id: uuid.UUID | None = Query(None),
) -> AlertListResponse:
    async with AsyncSessionLocal() as session:
        stmt = select(Alert).order_by(Alert.name)
        if project_id is not None:
            stmt = stmt.where(Alert.project_id == project_id)
        rows = (await session.execute(stmt)).scalars().all()
        return AlertListResponse(
            alerts=[AlertResponse.model_validate(r) for r in rows], total=len(rows)
        )


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(alert_id: uuid.UUID, payload: AlertUpdate) -> AlertResponse:
    _validate(payload.metric, payload.comparator)
    async with AsyncSessionLocal() as session:
        row = await session.get(Alert, alert_id)
        if row is None:
            raise HTTPException(404, "Alert not found")
        for field in (
            "name",
            "metric",
            "comparator",
            "threshold",
            "window_minutes",
            "enabled",
        ):
            v = getattr(payload, field)
            if v is not None:
                setattr(row, field, v)
        await session.commit()
        await session.refresh(row)
        return AlertResponse.model_validate(row)


@router.delete("/{alert_id}", status_code=204)
async def delete_alert(alert_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(Alert, alert_id)
        if row is None:
            raise HTTPException(404, "Alert not found")
        await session.delete(row)
        await session.commit()


@router.post("/{alert_id}/check", response_model=AlertCheckResponse)
async def check_alert(alert_id: uuid.UUID) -> AlertCheckResponse:
    """Evaluate the alert now; persist the result on the row."""
    async with AsyncSessionLocal() as session:
        row = await session.get(Alert, alert_id)
        if row is None:
            raise HTTPException(404, "Alert not found")
        value = await evaluate_metric(
            session,
            project_id=row.project_id,
            metric=row.metric,
            window_minutes=row.window_minutes,
        )
        triggered = is_triggered(value, row.comparator, float(row.threshold))
        row.last_checked_at = datetime.now(UTC)
        row.last_value = value
        row.last_triggered = triggered
        await session.commit()
        return AlertCheckResponse(
            alert_id=row.id,
            metric=row.metric,
            value=value,
            threshold=float(row.threshold),
            comparator=row.comparator,
            triggered=triggered,
            checked_at=row.last_checked_at,
        )
