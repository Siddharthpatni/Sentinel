"""Celery task for persisting trace records into Postgres."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.db.models import Trace
from app.db.session import get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

AUTO_TRIAGE_RISK_TIERS = {"high", "unacceptable"}


def _should_auto_triage(trace: Trace) -> bool:
    """Decide whether a freshly-persisted trace warrants an automatic triage run.

    Skips the judge's and the triage agent's own self-calls
    (`_sentinel.is_judge` / `_sentinel.is_agent`, set in
    app/workers/evaluate_trace.py and app/agents/triage.py respectively) —
    otherwise a failing diagnostic/planner LLM call would recursively spawn
    another triage run on itself.
    """
    body = trace.request_body or {}
    marker = body.get("_sentinel", {}) if isinstance(body, dict) else {}
    if marker.get("is_judge") or marker.get("is_agent"):
        return False
    return trace.status_code >= 400 or trace.risk_tier in AUTO_TRIAGE_RISK_TIERS


@celery_app.task(bind=True, max_retries=3, default_retry_delay=5)  # type: ignore[misc]
def persist_trace_task(self, payload: dict) -> str:  # type: ignore[no-untyped-def]
    """Write a trace record to the database.

    This runs in a Celery worker process using a synchronous session.

    Args:
        payload: Serialized trace data from :class:`TraceCreate`.

    Returns:
        The UUID of the persisted trace.
    """
    session = get_sync_session()
    try:
        trace = Trace(
            id=uuid.uuid4(),
            project_id=uuid.UUID(payload["project_id"]),
            provider=payload["provider"],
            model=payload["model"],
            latency_ms=payload.get("latency_ms", 0),
            prompt_tokens=payload.get("prompt_tokens", 0),
            completion_tokens=payload.get("completion_tokens", 0),
            cost_usd=payload.get("cost_usd", 0.0),
            status_code=payload.get("status_code", 200),
            request_body=payload.get("request_body"),
            response_body=payload.get("response_body"),
            error_message=payload.get("error_message"),
            risk_tier=payload.get("risk_tier"),
            session_id=(uuid.UUID(payload["session_id"]) if payload.get("session_id") else None),
            created_at=datetime.now(UTC),
        )
        session.add(trace)
        session.flush()

        try:
            from app.audit.ledger import append_for_trace
            append_for_trace(session, trace)
        except Exception as exc:
            logger.warning("Failed to append audit ledger entry for %s: %s", trace.id, exc)

        session.commit()
        logger.info("Persisted trace %s for %s/%s", trace.id, trace.provider, trace.model)
        try:
            from app.workers.evaluate_trace import evaluate_trace
            evaluate_trace.delay(str(trace.id))
        except Exception as exc:
            logger.warning("Failed to schedule verification for %s: %s", trace.id, exc)

        if _should_auto_triage(trace):
            try:
                from app.agents.triage import start_triage
                start_triage(session, trace)
                session.commit()
            except Exception as exc:
                logger.warning("Failed to auto-start triage for %s: %s", trace.id, exc)

        return str(trace.id)
    except Exception as exc:
        session.rollback()
        logger.error("Failed to persist trace: %s", exc)
        raise self.retry(exc=exc) from exc
    finally:
        session.close()
