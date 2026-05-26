"""Seed script to create the default project if it doesn't exist."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.config import settings
from app.db.models import Project

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_default_project(session: AsyncSession) -> None:
    """Create the default project and API key if not already present."""
    result = await session.execute(
        select(Project).where(Project.api_key == settings.default_project_api_key)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.info("Default project already exists: %s", existing.name)
        return

    project = Project(
        name=settings.default_project_name,
        api_key=settings.default_project_api_key,
    )
    session.add(project)
    await session.commit()
    logger.info(
        "Seeded default project '%s' with API key '%s'",
        project.name,
        project.api_key,
    )
