"""Celery task for persisting trace records into Postgres."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.db.models import Trace
from app.db.session import SyncSessionLocal, get_sync_session
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


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
            created_at=datetime.now(timezone.utc),
        )
        session.add(trace)
        session.commit()
        logger.info("Persisted trace %s for %s/%s", trace.id, trace.provider, trace.model)
        return str(trace.id)
    except Exception as exc:
        session.rollback()
        logger.error("Failed to persist trace: %s", exc)
        raise self.retry(exc=exc)
    finally:
        session.close()
