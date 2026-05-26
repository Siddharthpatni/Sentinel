"""Trace recorder — enqueues trace payloads to the Celery broker."""

from __future__ import annotations

import logging

from app.tracing.schema import TraceCreate

logger = logging.getLogger(__name__)


def record_trace(trace: TraceCreate) -> None:
    """Enqueue a trace record for async persistence via Celery.

    Imports the Celery task lazily to avoid circular imports.
    """
    from app.workers.persist_trace import persist_trace_task

    payload = trace.model_dump(mode="json")
    persist_trace_task.delay(payload)
    logger.debug(
        "Enqueued trace: provider=%s model=%s tokens=%d+%d",
        trace.provider,
        trace.model,
        trace.prompt_tokens,
        trace.completion_tokens,
    )
