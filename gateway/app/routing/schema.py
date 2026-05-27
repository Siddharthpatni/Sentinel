"""Pydantic schemas for routing policies."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    model: str
    max_cost_usd: float | None = None
    max_latency_ms: int | None = None


class FallbackOn(BaseModel):
    http_5xx: bool = True
    timeout: bool = True
    low_confidence: float | None = None


class RoutingPolicyCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    match_jsonpath: str
    candidates: list[Candidate] = Field(min_length=1, max_length=5)
    fallback_on: FallbackOn = Field(default_factory=FallbackOn)
    enabled: bool = True


class RoutingPolicyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    match_jsonpath: str | None = None
    candidates: list[Candidate] | None = Field(default=None, min_length=1, max_length=5)
    fallback_on: FallbackOn | None = None
    enabled: bool | None = None


class RoutingPolicyResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    match_jsonpath: str
    candidates: list[dict]
    fallback_on: dict
    enabled: bool

    model_config = {"from_attributes": True}


class RoutingPolicyListResponse(BaseModel):
    policies: list[RoutingPolicyResponse]
    total: int
