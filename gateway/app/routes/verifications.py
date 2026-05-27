"""CRUD routes for verification rules."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db.models import Project, Verification, VerificationRule
from app.db.session import AsyncSessionLocal
from app.verification.schema import (
    VerificationListResponse,
    VerificationResponse,
    VerificationRuleCreate,
    VerificationRuleListResponse,
    VerificationRuleResponse,
    VerificationRuleUpdate,
)

router = APIRouter(prefix="/api/verification-rules", tags=["verification-rules"])
verifications_router = APIRouter(prefix="/api/verifications", tags=["verifications"])


@verifications_router.get("", response_model=VerificationListResponse)
async def list_verifications(
    trace_id: uuid.UUID | None = Query(None),
    verdict: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> VerificationListResponse:
    async with AsyncSessionLocal() as session:
        query = select(Verification).order_by(Verification.created_at.desc())
        count_query = select(func.count()).select_from(Verification)
        if trace_id is not None:
            query = query.where(Verification.trace_id == trace_id)
            count_query = count_query.where(Verification.trace_id == trace_id)
        if verdict is not None:
            query = query.where(Verification.verdict == verdict)
            count_query = count_query.where(Verification.verdict == verdict)
        result = await session.execute(query.limit(limit))
        rows = result.scalars().all()
        total = (await session.execute(count_query)).scalar_one()
        return VerificationListResponse(
            verifications=[VerificationResponse.model_validate(r) for r in rows],
            next_cursor=None,
            total_count=total,
        )


@router.post("", response_model=VerificationRuleResponse, status_code=201)
async def create_rule(payload: VerificationRuleCreate) -> VerificationRuleResponse:
    async with AsyncSessionLocal() as session:
        project = await session.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        rule = VerificationRule(
            project_id=payload.project_id,
            name=payload.name,
            match_jsonpath=payload.match_jsonpath,
            sample_rate=payload.sample_rate,
            judge_model=payload.judge_model,
            judge_prompt_template=payload.judge_prompt_template,
            enabled=payload.enabled,
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return VerificationRuleResponse.model_validate(rule)


@router.get("", response_model=VerificationRuleListResponse)
async def list_rules(
    project_id: uuid.UUID | None = Query(None),
    enabled: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> VerificationRuleListResponse:
    async with AsyncSessionLocal() as session:
        query = select(VerificationRule).order_by(VerificationRule.name)
        count_query = select(func.count()).select_from(VerificationRule)

        if project_id is not None:
            query = query.where(VerificationRule.project_id == project_id)
            count_query = count_query.where(VerificationRule.project_id == project_id)
        if enabled is not None:
            query = query.where(VerificationRule.enabled == enabled)
            count_query = count_query.where(VerificationRule.enabled == enabled)

        result = await session.execute(query.limit(limit))
        rules = result.scalars().all()
        total = (await session.execute(count_query)).scalar_one()

        return VerificationRuleListResponse(
            rules=[VerificationRuleResponse.model_validate(r) for r in rules],
            total=total,
        )


@router.get("/{rule_id}", response_model=VerificationRuleResponse)
async def get_rule(rule_id: uuid.UUID) -> VerificationRuleResponse:
    async with AsyncSessionLocal() as session:
        rule = await session.get(VerificationRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        return VerificationRuleResponse.model_validate(rule)


@router.patch("/{rule_id}", response_model=VerificationRuleResponse)
async def update_rule(
    rule_id: uuid.UUID, payload: VerificationRuleUpdate
) -> VerificationRuleResponse:
    async with AsyncSessionLocal() as session:
        rule = await session.get(VerificationRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)

        await session.commit()
        await session.refresh(rule)
        return VerificationRuleResponse.model_validate(rule)


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(rule_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        rule = await session.get(VerificationRule, rule_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Rule not found")
        await session.delete(rule)
        await session.commit()
