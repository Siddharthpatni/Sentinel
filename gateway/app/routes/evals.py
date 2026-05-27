"""CRUD + run routes for eval suites (Step 12)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.db.models import Eval, EvalCase, EvalRun, Project
from app.db.session import AsyncSessionLocal, get_sync_session
from app.evals.parser import parse_suite_yaml
from app.evals.runner import run_suite

router = APIRouter(prefix="/api/evals", tags=["evals"])


class EvalCreate(BaseModel):
    project_id: uuid.UUID
    yaml_source: str = Field(min_length=1)


class EvalResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    yaml_source: str

    model_config = {"from_attributes": True}


class EvalListResponse(BaseModel):
    evals: list[EvalResponse]
    total: int


class EvalRunResponse(BaseModel):
    id: uuid.UUID
    eval_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    total: int
    passed: int
    failed: int
    triggered_by: str
    git_sha: str | None

    model_config = {"from_attributes": True}


class EvalRunListResponse(BaseModel):
    runs: list[EvalRunResponse]
    total: int


class EvalCaseResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    case_name: str
    input: dict
    actual: dict | None
    passed: bool
    assertion_log: list[dict]
    trace_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class EvalRunDetailResponse(BaseModel):
    run: EvalRunResponse
    cases: list[EvalCaseResponse]


class EvalRunCreate(BaseModel):
    triggered_by: str = Field(default="manual", max_length=20)
    git_sha: str | None = Field(default=None, max_length=64)


@router.post("", response_model=EvalResponse, status_code=201)
async def create_eval(payload: EvalCreate) -> EvalResponse:
    try:
        suite = parse_suite_yaml(payload.yaml_source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid YAML suite: {exc}") from exc

    async with AsyncSessionLocal() as session:
        project = await session.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        existing = await session.execute(
            select(Eval).where(
                Eval.project_id == payload.project_id,
                Eval.name == suite.name,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            row.yaml_source = payload.yaml_source
        else:
            row = Eval(
                project_id=payload.project_id,
                name=suite.name,
                yaml_source=payload.yaml_source,
            )
            session.add(row)
        await session.commit()
        await session.refresh(row)
        return EvalResponse.model_validate(row)


@router.get("", response_model=EvalListResponse)
async def list_evals(
    project_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> EvalListResponse:
    async with AsyncSessionLocal() as session:
        query = select(Eval).order_by(Eval.name)
        count_query = select(func.count()).select_from(Eval)
        if project_id is not None:
            query = query.where(Eval.project_id == project_id)
            count_query = count_query.where(Eval.project_id == project_id)
        result = await session.execute(query.limit(limit))
        evals = result.scalars().all()
        total = (await session.execute(count_query)).scalar_one()
        return EvalListResponse(
            evals=[EvalResponse.model_validate(e) for e in evals],
            total=total,
        )


@router.delete("/{eval_id}", status_code=204)
async def delete_eval(eval_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(Eval, eval_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Eval not found")
        await session.delete(row)
        await session.commit()


@router.post("/{eval_id}/run", response_model=EvalRunResponse, status_code=201)
async def run_eval(eval_id: uuid.UUID, payload: EvalRunCreate | None = None) -> EvalRunResponse:
    """Execute an eval suite synchronously and return the run summary.

    The suite is run in-process using a sync session because the runner POSTs
    back through the gateway to capture traces. Eval suites are bounded (≤ a
    few dozen cases in practice) so blocking the request is acceptable.
    """
    payload = payload or EvalRunCreate()
    async with AsyncSessionLocal() as session:
        eval_row = await session.get(Eval, eval_id)
        if eval_row is None:
            raise HTTPException(status_code=404, detail="Eval not found")

    sync_session = get_sync_session()
    try:
        eval_row_sync = sync_session.get(Eval, eval_id)
        if eval_row_sync is None:
            raise HTTPException(status_code=404, detail="Eval not found")
        run = run_suite(
            sync_session,
            eval_row_sync,
            triggered_by=payload.triggered_by,
            git_sha=payload.git_sha,
        )
        return EvalRunResponse.model_validate(run)
    finally:
        sync_session.close()


@router.get("/{eval_id}/runs", response_model=EvalRunListResponse)
async def list_runs(
    eval_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=200),
) -> EvalRunListResponse:
    async with AsyncSessionLocal() as session:
        eval_row = await session.get(Eval, eval_id)
        if eval_row is None:
            raise HTTPException(status_code=404, detail="Eval not found")
        result = await session.execute(
            select(EvalRun)
            .where(EvalRun.eval_id == eval_id)
            .order_by(EvalRun.started_at.desc())
            .limit(limit)
        )
        runs = result.scalars().all()
        total = (
            await session.execute(
                select(func.count()).select_from(EvalRun).where(EvalRun.eval_id == eval_id)
            )
        ).scalar_one()
        return EvalRunListResponse(
            runs=[EvalRunResponse.model_validate(r) for r in runs],
            total=total,
        )


@router.get("/{eval_id}/trends")
async def get_trends(eval_id: uuid.UUID, limit: int = Query(50, ge=1, le=500)) -> dict:
    """Pass/fail trend across the most recent runs (oldest → newest)."""
    async with AsyncSessionLocal() as session:
        if await session.get(Eval, eval_id) is None:
            raise HTTPException(status_code=404, detail="Eval not found")
        result = await session.execute(
            select(EvalRun)
            .where(EvalRun.eval_id == eval_id)
            .order_by(EvalRun.started_at.desc())
            .limit(limit)
        )
        runs = list(result.scalars().all())
        runs.reverse()
        return {
            "points": [
                {
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                    "total": r.total,
                    "passed": r.passed,
                    "failed": r.failed,
                    "pass_rate": (r.passed / r.total) if r.total else 0.0,
                    "git_sha": r.git_sha,
                }
                for r in runs
            ]
        }


@router.get("/{eval_id}/runs/{run_id}", response_model=EvalRunDetailResponse)
async def get_run_detail(eval_id: uuid.UUID, run_id: uuid.UUID) -> EvalRunDetailResponse:
    async with AsyncSessionLocal() as session:
        run = await session.get(EvalRun, run_id)
        if run is None or run.eval_id != eval_id:
            raise HTTPException(status_code=404, detail="Run not found")
        result = await session.execute(
            select(EvalCase).where(EvalCase.run_id == run_id).order_by(EvalCase.case_name)
        )
        cases = result.scalars().all()
        return EvalRunDetailResponse(
            run=EvalRunResponse.model_validate(run),
            cases=[EvalCaseResponse.model_validate(c) for c in cases],
        )
