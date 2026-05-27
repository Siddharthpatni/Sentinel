"""Read-only project listing route."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Project
from app.db.session import AsyncSessionLocal

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]


@router.get("", response_model=ProjectListResponse)
async def list_projects() -> ProjectListResponse:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Project).order_by(Project.created_at))
        projects = result.scalars().all()
        return ProjectListResponse(
            projects=[ProjectResponse.model_validate(p) for p in projects]
        )
