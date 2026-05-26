"""Unit tests for the trace Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.tracing.schema import TraceCreate, TraceResponse, TraceStats


class TestTraceCreate:
    """Tests for TraceCreate schema."""

    def test_minimal_creation(self) -> None:
        """Should create with just required fields."""
        trace = TraceCreate(
            project_id=uuid.uuid4(),
            provider="openai",
            model="gpt-4o",
        )
        assert trace.latency_ms == 0
        assert trace.prompt_tokens == 0
        assert trace.cost_usd == 0.0
        assert trace.status_code == 200
        assert trace.request_body is None
        assert trace.error_message is None

    def test_full_creation(self) -> None:
        """Should accept all fields."""
        pid = uuid.uuid4()
        trace = TraceCreate(
            project_id=pid,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            latency_ms=1234,
            prompt_tokens=500,
            completion_tokens=200,
            cost_usd=0.0045,
            status_code=200,
            request_body={"messages": [{"role": "user", "content": "hi"}]},
            response_body={"content": [{"type": "text", "text": "hello"}]},
        )
        assert trace.project_id == pid
        assert trace.cost_usd == 0.0045

    def test_serialization_roundtrip(self) -> None:
        """Should serialize to dict and back."""
        trace = TraceCreate(
            project_id=uuid.uuid4(),
            provider="openai",
            model="gpt-4o",
            latency_ms=100,
        )
        data = trace.model_dump(mode="json")
        assert isinstance(data["project_id"], str)
        restored = TraceCreate(**data)
        assert restored.provider == "openai"


class TestTraceResponse:
    """Tests for TraceResponse schema."""

    def test_from_dict(self) -> None:
        """Should parse from a dictionary."""
        data = {
            "id": str(uuid.uuid4()),
            "project_id": str(uuid.uuid4()),
            "provider": "openai",
            "model": "gpt-4o",
            "latency_ms": 500,
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost_usd": 0.001,
            "status_code": 200,
            "created_at": datetime.now(UTC).isoformat(),
        }
        resp = TraceResponse(**data)
        assert resp.provider == "openai"
        assert resp.error_message is None


class TestTraceStats:
    """Tests for TraceStats schema."""

    def test_defaults(self) -> None:
        """Should have sensible defaults."""
        stats = TraceStats()
        assert stats.total_traces == 0
        assert stats.total_cost_usd == 0.0
        assert stats.traces_by_provider == {}
        assert stats.error_count == 0
