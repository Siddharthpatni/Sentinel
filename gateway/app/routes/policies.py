"""CRUD routes for routing policies."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db.models import Project, RoutingPolicy
from app.db.session import AsyncSessionLocal
from app.routing.schema import (
    RoutingPolicyCreate,
    RoutingPolicyListResponse,
    RoutingPolicyResponse,
    RoutingPolicyUpdate,
)

router = APIRouter(prefix="/api/routing-policies", tags=["routing-policies"])


@router.post("", response_model=RoutingPolicyResponse, status_code=201)
async def create_policy(payload: RoutingPolicyCreate) -> RoutingPolicyResponse:
    async with AsyncSessionLocal() as session:
        project = await session.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        policy = RoutingPolicy(
            project_id=payload.project_id,
            name=payload.name,
            match_jsonpath=payload.match_jsonpath,
            candidates=[c.model_dump() for c in payload.candidates],
            fallback_on=payload.fallback_on.model_dump(),
            enabled=payload.enabled,
        )
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return RoutingPolicyResponse.model_validate(policy)


@router.get("", response_model=RoutingPolicyListResponse)
async def list_policies(
    project_id: uuid.UUID | None = Query(None),
    enabled: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> RoutingPolicyListResponse:
    async with AsyncSessionLocal() as session:
        query = select(RoutingPolicy).order_by(RoutingPolicy.name)
        count_query = select(func.count()).select_from(RoutingPolicy)

        if project_id is not None:
            query = query.where(RoutingPolicy.project_id == project_id)
            count_query = count_query.where(RoutingPolicy.project_id == project_id)
        if enabled is not None:
            query = query.where(RoutingPolicy.enabled == enabled)
            count_query = count_query.where(RoutingPolicy.enabled == enabled)

        result = await session.execute(query.limit(limit))
        policies = result.scalars().all()
        total = (await session.execute(count_query)).scalar_one()

        return RoutingPolicyListResponse(
            policies=[RoutingPolicyResponse.model_validate(p) for p in policies],
            total=total,
        )


@router.patch("/{policy_id}", response_model=RoutingPolicyResponse)
async def update_policy(
    policy_id: uuid.UUID, payload: RoutingPolicyUpdate
) -> RoutingPolicyResponse:
    async with AsyncSessionLocal() as session:
        policy = await session.get(RoutingPolicy, policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")

        data = payload.model_dump(exclude_unset=True)
        if "candidates" in data and data["candidates"] is not None:
            data["candidates"] = [c for c in data["candidates"]]
        for field, value in data.items():
            setattr(policy, field, value)

        await session.commit()
        await session.refresh(policy)
        return RoutingPolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(policy_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        policy = await session.get(RoutingPolicy, policy_id)
        if policy is None:
            raise HTTPException(status_code=404, detail="Policy not found")
        await session.delete(policy)
        await session.commit()
