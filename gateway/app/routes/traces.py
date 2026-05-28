"""Dashboard/Admin API routes for inspecting traces."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select

from app.db.models import Project, Span, Trace, TraceAnnotation
from app.db.session import AsyncSessionLocal
from app.tracing.schema import (
    SpanBatchIngest,
    SpanResponse,
    TraceListResponse,
    TraceResponse,
    TraceStats,
)

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
            except ValueError as err:
                raise HTTPException(status_code=400, detail="Invalid cursor format") from err

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


class TimeseriesPoint(BaseModel):
    bucket: datetime
    count: int
    cost_usd: float
    avg_latency_ms: float


class TimeseriesResponse(BaseModel):
    bucket: str
    points: list[TimeseriesPoint]


@router.get("/timeseries", response_model=TimeseriesResponse)
async def get_timeseries(
    hours: int = Query(24, ge=1, le=720),
    bucket: str = Query("hour", pattern="^(hour|day)$"),
    project_id: uuid.UUID | None = Query(None),
) -> TimeseriesResponse:
    """Return cost / call-count buckets for the last ``hours``.

    Used by the dashboard cost-over-time sparkline.
    """
    since = datetime.now(UTC) - timedelta(hours=hours)
    trunc = func.date_trunc(bucket, Trace.created_at)
    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                trunc.label("bucket"),
                func.count(Trace.id).label("count"),
                func.coalesce(func.sum(Trace.cost_usd), 0).label("cost"),
                func.coalesce(func.avg(Trace.latency_ms), 0).label("lat"),
            )
            .where(Trace.created_at >= since)
            .group_by(trunc)
            .order_by(trunc)
        )
        if project_id is not None:
            stmt = stmt.where(Trace.project_id == project_id)
        rows = (await session.execute(stmt)).all()
        return TimeseriesResponse(
            bucket=bucket,
            points=[
                TimeseriesPoint(
                    bucket=r.bucket,
                    count=int(r.count),
                    cost_usd=float(r.cost),
                    avg_latency_ms=float(r.lat),
                )
                for r in rows
            ],
        )


@router.get("/queues/unannotated", response_model=TraceListResponse)
async def list_unannotated(
    limit: int = Query(50, ge=1, le=200),
) -> TraceListResponse:
    """Traces with no annotations yet — feeds the human-review queue."""
    async with AsyncSessionLocal() as session:
        annotated = select(TraceAnnotation.trace_id).distinct()
        stmt = (
            select(Trace)
            .where(Trace.id.notin_(annotated))
            .order_by(desc(Trace.created_at))
            .limit(limit)
        )
        rows = (await session.execute(stmt)).scalars().all()
        total = (
            await session.execute(
                select(func.count(Trace.id)).where(Trace.id.notin_(annotated))
            )
        ).scalar_one()
        return TraceListResponse(
            traces=[TraceResponse.model_validate(t) for t in rows],
            next_cursor=None,
            total_count=int(total),
        )


@router.get("/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: uuid.UUID) -> TraceResponse:
    """Get a single trace by ID, including its span tree (flat list)."""
    async with AsyncSessionLocal() as session:
        trace = await session.get(Trace, trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        span_rows = (
            await session.execute(
                select(Span).where(Span.trace_id == trace_id).order_by(Span.start_ts)
            )
        ).scalars().all()
        resp = TraceResponse.model_validate(trace)
        resp.spans = [SpanResponse.model_validate(s) for s in span_rows]
        return resp


@router.post("/{trace_id}/spans", status_code=202)
async def ingest_spans(
    trace_id: uuid.UUID,
    payload: SpanBatchIngest,
    x_sentinel_key: str | None = Header(None),
) -> dict:
    """Ingest a batch of spans for a trace.

    If the parent trace row does not yet exist, a shell Trace is created
    with derived latency and provider/model from the payload. Existing
    spans for ``trace_id`` are preserved; this endpoint only appends.
    """
    if not x_sentinel_key:
        raise HTTPException(status_code=401, detail="Missing Sentinel API key")

    async with AsyncSessionLocal() as session:
        from app.auth import resolve_project_by_key

        project = await resolve_project_by_key(session, x_sentinel_key)
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        trace = await session.get(Trace, trace_id)
        if trace is None:
            duration_ms = int(
                (payload.end_ts - payload.start_ts).total_seconds() * 1000
            )
            trace = Trace(
                id=trace_id,
                project_id=project.id,
                provider=payload.provider,
                model=payload.model,
                latency_ms=max(duration_ms, 0),
                status_code=200,
                created_at=payload.start_ts,
                request_body={"trace_name": payload.name},
                response_body=None,
            )
            session.add(trace)
            await session.flush()
        elif trace.project_id != project.id:
            raise HTTPException(status_code=403, detail="Trace belongs to another project")

        for s in payload.spans:
            session.add(
                Span(
                    id=s.id,
                    trace_id=trace_id,
                    parent_span_id=s.parent_span_id,
                    name=s.name,
                    span_type=s.span_type,
                    start_ts=s.start_ts,
                    end_ts=s.end_ts,
                    status=s.status,
                    attributes=s.attributes,
                )
            )
        await session.commit()
        return {"trace_id": str(trace_id), "spans_ingested": len(payload.spans)}
