"""Autonomous incident-triage API + WebSocket routes.

Endpoints:
  - POST /api/v1/triage/trigger              start a triage run for a trace
  - GET  /api/v1/triage/{execution_id}        current state + diagnosis + patch
  - POST /api/v1/triage/{execution_id}/approve   approve/reject the proposed fix
  - POST /api/v1/triage/simulate              1-click demo: synthetic failing trace
  - WS   /ws/triage/{execution_id}            live node-transition stream

Unauthenticated, like the rest of the dashboard-facing surface (traces,
alerts, annotations, credentials) — app.auth.get_current_user is only wired
up on the settings/keys API-key-management endpoints so far, and the
dashboard has no login page or credentialed fetch calls yet. Gating this
feature alone behind a login flow that doesn't exist in the frontend would
make it the one page recruiters/evaluators can't actually click through.
`TriageApproval.user_id` stays null until real dashboard auth lands.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

import redis.asyncio as aioredis
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.triage import log_triage_decision, run_diagnostic_node, run_execution_node
from app.config import settings
from app.db.models import Project, Trace, TriageApproval, TriageExecution
from app.db.session import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/triage", tags=["triage"])
ws_router = APIRouter(prefix="/ws/triage", tags=["triage-ws"])


class TriageTriggerRequest(BaseModel):
    trace_id: uuid.UUID


class TriageApproveRequest(BaseModel):
    action: str = Field(pattern=r"^(approve|reject)$")
    comment: str | None = None


class TriageExecutionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    trace_id: uuid.UUID
    status: str
    current_node: str
    diagnosis: dict | None
    proposed_patch: dict | None
    patch_risk_tier: str | None
    compliance_reasons: list[str]
    pr_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    # EU-AI-Act tier of the *originating trace* (app.audit.classifiers), shown
    # alongside patch_risk_tier for the Compliance Badge. A different axis —
    # see app/agents/risk.py's module docstring.
    trace_risk_tier: str | None


class TriageExecutionListResponse(BaseModel):
    executions: list[TriageExecutionResponse]
    total: int


def _to_response(execution: TriageExecution, trace: Trace | None) -> TriageExecutionResponse:
    return TriageExecutionResponse(
        id=execution.id,
        project_id=execution.project_id,
        trace_id=execution.trace_id,
        status=execution.status,
        current_node=execution.current_node,
        diagnosis=execution.diagnosis,
        proposed_patch=execution.proposed_patch,
        patch_risk_tier=execution.patch_risk_tier,
        compliance_reasons=execution.compliance_reasons,
        pr_url=execution.pr_url,
        error_message=execution.error_message,
        created_at=execution.created_at,
        updated_at=execution.updated_at,
        trace_risk_tier=trace.risk_tier if trace else None,
    )


@router.get("", response_model=TriageExecutionListResponse)
async def list_triage_executions(
    project_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_async_session),
) -> TriageExecutionListResponse:
    stmt = select(TriageExecution).order_by(TriageExecution.created_at.desc()).limit(limit)
    if project_id is not None:
        stmt = stmt.where(TriageExecution.project_id == project_id)
    rows = list((await session.execute(stmt)).scalars().all())

    trace_ids = {r.trace_id for r in rows}
    traces_by_id: dict[uuid.UUID, Trace] = {}
    if trace_ids:
        trace_rows = (
            await session.execute(select(Trace).where(Trace.id.in_(trace_ids)))
        ).scalars()
        traces_by_id = {t.id: t for t in trace_rows}

    return TriageExecutionListResponse(
        executions=[_to_response(r, traces_by_id.get(r.trace_id)) for r in rows],
        total=len(rows),
    )


@router.post("/trigger", response_model=TriageExecutionResponse, status_code=status.HTTP_201_CREATED)
async def trigger_triage(
    payload: TriageTriggerRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TriageExecutionResponse:
    trace = await session.get(Trace, payload.trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")

    execution = TriageExecution(project_id=trace.project_id, trace_id=trace.id)
    session.add(execution)
    await session.flush()
    await session.commit()
    await session.refresh(execution)
    run_diagnostic_node.delay(str(execution.id))
    return _to_response(execution, trace)


@router.get("/{execution_id}", response_model=TriageExecutionResponse)
async def get_triage_execution(
    execution_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
) -> TriageExecutionResponse:
    execution = await session.get(TriageExecution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="triage execution not found")
    trace = await session.get(Trace, execution.trace_id)
    return _to_response(execution, trace)


@router.post("/{execution_id}/approve", response_model=TriageExecutionResponse)
async def approve_triage_execution(
    execution_id: uuid.UUID,
    payload: TriageApproveRequest,
    session: AsyncSession = Depends(get_async_session),
) -> TriageExecutionResponse:
    execution = await session.get(TriageExecution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="triage execution not found")
    if execution.status != "paused_for_approval":
        raise HTTPException(
            status_code=409,
            detail=f"execution is '{execution.status}', not awaiting approval",
        )

    approval = TriageApproval(
        execution_id=execution.id,
        user_id=None,
        action=payload.action,
        comment=payload.comment,
    )
    session.add(approval)
    execution.status = "approved" if payload.action == "approve" else "rejected"
    await session.flush()
    await session.commit()
    await session.refresh(execution)

    log_triage_decision.delay(str(execution.id), str(approval.id))
    if payload.action == "approve":
        run_execution_node.delay(str(execution.id))

    trace = await session.get(Trace, execution.trace_id)
    return _to_response(execution, trace)


@router.post("/simulate", response_model=TriageExecutionResponse, status_code=status.HTTP_201_CREATED)
async def simulate_triage(
    session: AsyncSession = Depends(get_async_session),
) -> TriageExecutionResponse:
    """Create a synthetic failing trace and kick off triage — 1-click demo path."""
    result = await session.execute(
        select(Project).where(Project.api_key == settings.default_project_api_key)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="default project not seeded")

    trace = Trace(
        project_id=project.id,
        provider="openai",
        model="gpt-4o-mini",
        latency_ms=842,
        prompt_tokens=128,
        completion_tokens=0,
        cost_usd=0.0002,
        status_code=500,
        request_body={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Summarize this document: {{doc}}"}],
        },
        response_body={
            "error": {
                "message": "'NoneType' object has no attribute 'strip'",
                "type": "server_error",
            }
        },
        error_message="'NoneType' object has no attribute 'strip'",
        risk_tier="limited",
    )
    session.add(trace)
    await session.flush()

    execution = TriageExecution(project_id=project.id, trace_id=trace.id)
    session.add(execution)
    await session.flush()
    await session.commit()
    await session.refresh(execution)

    run_diagnostic_node.delay(str(execution.id))
    return _to_response(execution, trace)


@ws_router.websocket("/{execution_id}")
async def triage_ws(websocket: WebSocket, execution_id: uuid.UUID) -> None:
    """Stream node-transition events for one execution over Redis pub/sub.

    Each triage node task publishes to `triage:{execution_id}` (see
    app/agents/triage.py::_publish_event) from the Celery worker process;
    this bridges that channel into the browser's WebSocket connection.
    """
    await websocket.accept()
    client = aioredis.from_url(settings.redis_url)
    pubsub = client.pubsub()
    channel = f"triage:{execution_id}"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message["data"]
            await websocket.send_text(data if isinstance(data, str) else data.decode("utf-8"))
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()
        await client.close()
