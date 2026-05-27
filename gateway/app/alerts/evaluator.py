"""Alert evaluators — pure functions that compute a metric over a window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Trace

ALLOWED_METRICS = {"cost_per_hour_usd", "error_rate_pct", "latency_p95_ms"}
ALLOWED_COMPARATORS = {"gt", "lt"}


async def evaluate_metric(
    session: AsyncSession,
    *,
    project_id,  # type: ignore[no-untyped-def]
    metric: str,
    window_minutes: int,
) -> float:
    """Compute the current value of ``metric`` over the last ``window_minutes``."""
    cutoff = datetime.now(UTC) - timedelta(minutes=window_minutes)
    base = select(Trace).where(
        Trace.project_id == project_id, Trace.created_at >= cutoff
    )

    if metric == "cost_per_hour_usd":
        total = await session.scalar(
            select(func.coalesce(func.sum(Trace.cost_usd), 0)).where(
                Trace.project_id == project_id, Trace.created_at >= cutoff
            )
        )
        # Normalize to a per-hour rate so thresholds are window-independent.
        hours = max(window_minutes / 60.0, 1e-6)
        return float(total or 0) / hours

    if metric == "error_rate_pct":
        total = await session.scalar(
            select(func.count(Trace.id)).where(
                Trace.project_id == project_id, Trace.created_at >= cutoff
            )
        )
        errors = await session.scalar(
            select(func.count(Trace.id)).where(
                Trace.project_id == project_id,
                Trace.created_at >= cutoff,
                Trace.status_code >= 400,
            )
        )
        if not total:
            return 0.0
        return float(errors or 0) / float(total) * 100.0

    if metric == "latency_p95_ms":
        # Postgres percentile_cont; fall back to a Python sort if not available.
        try:
            val = await session.scalar(
                select(
                    func.percentile_cont(0.95).within_group(Trace.latency_ms.asc())
                ).where(
                    Trace.project_id == project_id, Trace.created_at >= cutoff
                )
            )
            return float(val or 0)
        except Exception:
            rows = (await session.execute(base.order_by(Trace.latency_ms))).scalars().all()
            if not rows:
                return 0.0
            idx = max(0, int(len(rows) * 0.95) - 1)
            return float(rows[idx].latency_ms)

    raise ValueError(f"Unknown metric: {metric}")


def is_triggered(value: float, comparator: str, threshold: float) -> bool:
    if comparator == "gt":
        return value > threshold
    if comparator == "lt":
        return value < threshold
    raise ValueError(f"Unknown comparator: {comparator}")
