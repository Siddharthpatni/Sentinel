"""Sentinel tracing — span tree emission for agent runs.

Usage::

    from sentinel import trace

    with trace("research_agent", sentinel_api_key="sk-...") as t:
        with t.span("plan", span_type="llm"):
            ...
        with t.span("search", span_type="tool", query=q):
            ...

Spans are buffered in-process and flushed to the gateway on trace exit.
Failures during flush are swallowed — tracing never breaks user code.
"""

from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterator

import httpx

_DEFAULT_SENTINEL_URL = "http://localhost:8000"

_current_trace: contextvars.ContextVar["Trace | None"] = contextvars.ContextVar(
    "sentinel_current_trace", default=None
)
_current_span: contextvars.ContextVar["SpanRecord | None"] = contextvars.ContextVar(
    "sentinel_current_span", default=None
)


@dataclass
class SpanRecord:
    id: str
    parent_span_id: str | None
    name: str
    span_type: str
    start_ts: float
    end_ts: float | None = None
    status: str = "ok"
    attributes: dict[str, Any] = field(default_factory=dict)

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def to_wire(self) -> dict[str, Any]:
        d = asdict(self)
        d["start_ts"] = datetime.fromtimestamp(self.start_ts, UTC).isoformat()
        d["end_ts"] = (
            datetime.fromtimestamp(self.end_ts, UTC).isoformat()
            if self.end_ts is not None
            else None
        )
        return d


class Trace:
    """A single agent run. Holds buffered spans, flushed on exit."""

    def __init__(
        self,
        name: str,
        *,
        sentinel_url: str,
        sentinel_api_key: str,
        provider: str = "agent",
        model: str = "n/a",
    ) -> None:
        self.id = str(uuid.uuid4())
        self.name = name
        self.provider = provider
        self.model = model
        self._sentinel_url = sentinel_url.rstrip("/")
        self._sentinel_api_key = sentinel_api_key
        self._spans: list[SpanRecord] = []
        self._start_ts = time.time()
        self._end_ts: float | None = None

    @contextmanager
    def span(
        self, name: str, *, span_type: str = "custom", **attributes: Any
    ) -> Iterator[SpanRecord]:
        parent = _current_span.get()
        rec = SpanRecord(
            id=str(uuid.uuid4()),
            parent_span_id=parent.id if parent is not None else None,
            name=name,
            span_type=span_type,
            start_ts=time.time(),
            attributes=dict(attributes),
        )
        self._spans.append(rec)
        token = _current_span.set(rec)
        try:
            yield rec
        except Exception as e:
            rec.status = "error"
            rec.attributes["error"] = repr(e)
            raise
        finally:
            rec.end_ts = time.time()
            _current_span.reset(token)

    def flush(self) -> None:
        """POST buffered spans to the gateway. Errors are swallowed."""
        if not self._spans:
            return
        try:
            httpx.post(
                f"{self._sentinel_url}/api/traces/{self.id}/spans",
                headers={"x-sentinel-key": self._sentinel_api_key},
                json={
                    "name": self.name,
                    "provider": self.provider,
                    "model": self.model,
                    "start_ts": datetime.fromtimestamp(self._start_ts, UTC).isoformat(),
                    "end_ts": datetime.fromtimestamp(
                        self._end_ts or time.time(), UTC
                    ).isoformat(),
                    "spans": [s.to_wire() for s in self._spans],
                },
                timeout=5.0,
            )
        except Exception:
            # tracing must never break user code
            pass


@contextmanager
def trace(
    name: str,
    *,
    sentinel_api_key: str = "sk-sentinel-dev-000",
    sentinel_url: str = _DEFAULT_SENTINEL_URL,
    provider: str = "agent",
    model: str = "n/a",
) -> Iterator[Trace]:
    """Top-level trace context. Opens a root span named ``name``."""
    t = Trace(
        name,
        sentinel_url=sentinel_url,
        sentinel_api_key=sentinel_api_key,
        provider=provider,
        model=model,
    )
    trace_token = _current_trace.set(t)
    try:
        with t.span(name, span_type="agent"):
            yield t
    finally:
        t._end_ts = time.time()
        t.flush()
        _current_trace.reset(trace_token)


def current_trace() -> Trace | None:
    return _current_trace.get()


def current_span() -> SpanRecord | None:
    return _current_span.get()
