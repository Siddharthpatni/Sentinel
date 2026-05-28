"""Seed script to create the default project if it doesn't exist."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.config import settings
from app.db.models import Org, OrgMember, Project, User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_default_project(session: AsyncSession) -> None:
    """Create the default project and API key if not already present.

    Also backfills a ``default`` Org and links the project to it, so legacy
    deployments transition cleanly when auth lands. No User is created
    automatically — operators sign up through ``/api/auth/signup``.
    """
    org = (
        await session.execute(select(Org).where(Org.slug == "default"))
    ).scalar_one_or_none()
    if org is None:
        org = Org(name="Default", slug="default")
        session.add(org)
        await session.flush()
        logger.info("Seeded default org")

    result = await session.execute(
        select(Project).where(Project.api_key == settings.default_project_api_key)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        if existing.org_id is None:
            existing.org_id = org.id
            await session.commit()
            logger.info("Linked default project to default org")
        else:
            logger.info("Default project already exists: %s", existing.name)
        return

    project = Project(
        name=settings.default_project_name,
        api_key=settings.default_project_api_key,
        org_id=org.id,
    )
    session.add(project)
    await session.commit()
    logger.info(
        "Seeded default project '%s' with API key '%s'",
        project.name,
        project.api_key,
    )


async def backfill_owner_membership(session: AsyncSession, user: User) -> None:
    """Make the first signed-up user an admin of the default org.

    Idempotent: skipped if the user is already a member.
    """
    org = (
        await session.execute(select(Org).where(Org.slug == "default"))
    ).scalar_one_or_none()
    if org is None:
        return
    existing = (
        await session.execute(
            select(OrgMember).where(
                OrgMember.org_id == org.id, OrgMember.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return
    session.add(OrgMember(org_id=org.id, user_id=user.id, role="admin"))
    await session.commit()
    logger.info("Backfilled default-org admin membership for %s", user.email)

