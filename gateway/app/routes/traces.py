"""Dashboard/Admin API routes for inspecting traces."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Trace
from app.db.session import AsyncSessionLocal
from app.tracing.schema import TraceListResponse, TraceResponse, TraceStats

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("", response_model=TraceListResponse)
async def list_traces(
    cursor: str | None = Query(None, description="Cursor for pagination (trace UUID)"),
    limit: int = Query(50, ge=1, le=200, description="Number of traces to return"),
    provider: str | None = Query(None, description="Filter by provider"),
    model: str | None = Query(None, description="Filter by model"),
) -> TraceListResponse:
    """List traces with cursor-based pagination, newest first."""
    async with AsyncSessionLocal() as session:
        query = select(Trace).order_by(desc(Trace.created_at), desc(Trace.id))

        # Apply filters
        if provider:
            query = query.where(Trace.provider == provider)
        if model:
            query = query.where(Trace.model == model)

        # Cursor-based pagination
        if cursor:
            try:
                cursor_uuid = uuid.UUID(cursor)
                cursor_trace = await session.get(Trace, cursor_uuid)
                if cursor_trace:
                    query = query.where(
                        (Trace.created_at < cursor_trace.created_at)
                        | (
                            (Trace.created_at == cursor_trace.created_at)
                            & (Trace.id < cursor_trace.id)
                        )
                    )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid cursor format")

        # Get total count (without cursor filter)
        count_query = select(func.count(Trace.id))
        if provider:
            count_query = count_query.where(Trace.provider == provider)
        if model:
            count_query = count_query.where(Trace.model == model)
        total_result = await session.execute(count_query)
        total_count = total_result.scalar() or 0

        # Fetch one extra to determine if there's a next page
        result = await session.execute(query.limit(limit + 1))
        traces = list(result.scalars().all())

        has_next = len(traces) > limit
        traces = traces[:limit]

        next_cursor = str(traces[-1].id) if has_next and traces else None

        return TraceListResponse(
            traces=[TraceResponse.model_validate(t) for t in traces],
            next_cursor=next_cursor,
            total_count=total_count,
        )


@router.get("/stats", response_model=TraceStats)
async def get_trace_stats() -> TraceStats:
    """Get aggregated trace statistics."""
    async with AsyncSessionLocal() as session:
        # Aggregate queries
        result = await session.execute(
            select(
                func.count(Trace.id).label("total"),
                func.coalesce(func.sum(Trace.cost_usd), 0).label("total_cost"),
                func.coalesce(func.avg(Trace.latency_ms), 0).label("avg_latency"),
                func.coalesce(func.sum(Trace.prompt_tokens), 0).label("total_prompt"),
                func.coalesce(func.sum(Trace.completion_tokens), 0).label("total_completion"),
                func.count(Trace.id).filter(Trace.status_code >= 400).label("errors"),
            )
        )
        row = result.one()

        # Provider breakdown
        provider_result = await session.execute(
            select(Trace.provider, func.count(Trace.id)).group_by(Trace.provider)
        )
        traces_by_provider = dict(provider_result.all())

        # Model breakdown
        model_result = await session.execute(
            select(Trace.model, func.count(Trace.id)).group_by(Trace.model)
        )
        traces_by_model = dict(model_result.all())

        return TraceStats(
            total_traces=row.total,
            total_cost_usd=float(row.total_cost),
            avg_latency_ms=float(row.avg_latency),
            total_prompt_tokens=int(row.total_prompt),
            total_completion_tokens=int(row.total_completion),
            traces_by_provider=traces_by_provider,
            traces_by_model=traces_by_model,
            error_count=row.errors,
        )


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: uuid.UUID) -> TraceResponse:
    """Get a single trace by ID."""
    async with AsyncSessionLocal() as session:
        trace = await session.get(Trace, trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        return TraceResponse.model_validate(trace)
