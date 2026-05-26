"""Pydantic schemas for trace data validation and serialization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import uuid
    from datetime import datetime


class TraceCreate(BaseModel):
    """Schema for creating a new trace record."""

    project_id: uuid.UUID
    provider: str
    model: str
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    status_code: int = 200
    request_body: dict | None = None
    response_body: dict | None = None
    error_message: str | None = None


class TraceResponse(BaseModel):
    """Schema for trace API responses."""

    id: uuid.UUID
    project_id: uuid.UUID
    provider: str
    model: str
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    status_code: int
    request_body: dict | None = None
    response_body: dict | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceListResponse(BaseModel):
    """Paginated list of traces."""

    traces: list[TraceResponse]
    next_cursor: str | None = None
    total_count: int = 0


class TraceStats(BaseModel):
    """Aggregated trace statistics."""

    total_traces: int = 0
    total_cost_usd: float = 0.0
    avg_latency_ms: float = 0.0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    traces_by_provider: dict[str, int] = Field(default_factory=dict)
    traces_by_model: dict[str, int] = Field(default_factory=dict)
    error_count: int = 0
