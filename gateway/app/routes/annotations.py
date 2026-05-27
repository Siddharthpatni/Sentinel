"""Trace annotations + sessions (LangSmith-style human feedback + threads)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select

from app.db.models import Project, Session, Trace, TraceAnnotation
from app.db.session import AsyncSessionLocal

ALLOWED_RATINGS = {"thumbs_up", "thumbs_down", "neutral"}

# ────────────────────────────────────────────────────────────────────
# Annotations
# ────────────────────────────────────────────────────────────────────

annotations_router = APIRouter(prefix="/api/annotations", tags=["annotations"])


class AnnotationCreate(BaseModel):
    trace_id: uuid.UUID
    rating: str
    dimension: str = Field(default="overall", max_length=40)
    comment: str | None = None
    author: str | None = None


class AnnotationResponse(BaseModel):
    id: uuid.UUID
    trace_id: uuid.UUID
    rating: str
    dimension: str
    comment: str | None
    author: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnnotationListResponse(BaseModel):
    annotations: list[AnnotationResponse]
    total: int


@annotations_router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(payload: AnnotationCreate) -> AnnotationResponse:
    if payload.rating not in ALLOWED_RATINGS:
        raise HTTPException(400, f"rating must be one of {sorted(ALLOWED_RATINGS)}")
    async with AsyncSessionLocal() as session:
        if await session.get(Trace, payload.trace_id) is None:
            raise HTTPException(404, "Trace not found")
        row = TraceAnnotation(
            trace_id=payload.trace_id,
            rating=payload.rating,
            dimension=payload.dimension,
            comment=payload.comment,
            author=payload.author,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return AnnotationResponse.model_validate(row)


@annotations_router.get("", response_model=AnnotationListResponse)
async def list_annotations(
    trace_id: uuid.UUID | None = Query(None),
    rating: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> AnnotationListResponse:
    async with AsyncSessionLocal() as session:
        stmt = select(TraceAnnotation).order_by(desc(TraceAnnotation.created_at)).limit(limit)
        if trace_id is not None:
            stmt = stmt.where(TraceAnnotation.trace_id == trace_id)
        if rating is not None:
            stmt = stmt.where(TraceAnnotation.rating == rating)
        rows = (await session.execute(stmt)).scalars().all()
        return AnnotationListResponse(
            annotations=[AnnotationResponse.model_validate(r) for r in rows],
            total=len(rows),
        )


@annotations_router.delete("/{annotation_id}", status_code=204)
async def delete_annotation(annotation_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(TraceAnnotation, annotation_id)
        if row is None:
            raise HTTPException(404, "Annotation not found")
        await session.delete(row)
        await session.commit()


# ────────────────────────────────────────────────────────────────────
# Sessions / Threads
# ────────────────────────────────────────────────────────────────────

sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str | None
    external_id: str
    metadata_json: dict
    created_at: datetime
    last_seen_at: datetime
    trace_count: int = 0

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class SessionTracesResponse(BaseModel):
    session: SessionResponse
    trace_ids: list[uuid.UUID]


@sessions_router.get("", response_model=SessionListResponse)
async def list_sessions(
    project_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> SessionListResponse:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                Session,
                func.count(Trace.id).label("trace_count"),
            )
            .outerjoin(Trace, Trace.session_id == Session.id)
            .group_by(Session.id)
            .order_by(desc(Session.last_seen_at))
            .limit(limit)
        )
        if project_id is not None:
            stmt = stmt.where(Session.project_id == project_id)
        rows = (await session.execute(stmt)).all()
        out = []
        for s, count in rows:
            resp = SessionResponse.model_validate(s)
            resp.trace_count = int(count or 0)
            out.append(resp)
        return SessionListResponse(sessions=out, total=len(out))


@sessions_router.get("/{session_id}", response_model=SessionTracesResponse)
async def get_session(session_id: uuid.UUID) -> SessionTracesResponse:
    async with AsyncSessionLocal() as session:
        s = await session.get(Session, session_id)
        if s is None:
            raise HTTPException(404, "Session not found")
        result = await session.execute(
            select(Trace.id)
            .where(Trace.session_id == session_id)
            .order_by(Trace.created_at)
        )
        return SessionTracesResponse(
            session=SessionResponse.model_validate(s),
            trace_ids=[r[0] for r in result.all()],
        )


@sessions_router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as session:
        s = await session.get(Session, session_id)
        if s is None:
            raise HTTPException(404, "Session not found")
        await session.delete(s)
        await session.commit()


async def resolve_session_id(project_id: uuid.UUID, body: dict) -> uuid.UUID | None:
    """Look up or create a session row from ``_sentinel.session_id`` in the body.

    Called at ingest time. Updates ``last_seen_at`` on every hit. Returns
    the internal Session UUID to stamp on the trace, or None if the request
    doesn't tag a session.
    """
    sentinel = body.get("_sentinel") or {}
    external_id = sentinel.get("session_id")
    if not external_id or not isinstance(external_id, str):
        return None
    name = sentinel.get("session_name")
    metadata = sentinel.get("session_metadata") or {}
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Session).where(
                Session.project_id == project_id,
                Session.external_id == external_id,
            )
        )
        row = result.scalar_one_or_none()
        now = datetime.now(UTC)
        if row is None:
            if await session.get(Project, project_id) is None:
                return None
            row = Session(
                project_id=project_id,
                external_id=external_id,
                name=name,
                metadata_json=metadata,
                last_seen_at=now,
            )
            session.add(row)
        else:
            row.last_seen_at = now
            if name and not row.name:
                row.name = name
        await session.commit()
        await session.refresh(row)
        return row.id
