"""Pydantic schemas for verification rules."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VerificationRuleCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    match_jsonpath: str = Field(..., min_length=1)
    sample_rate: float = Field(0.0, ge=0.0, le=1.0)
    judge_model: str = Field(..., min_length=1, max_length=100)
    judge_prompt_template: str = Field(..., min_length=1)
    enabled: bool = True


class VerificationRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    match_jsonpath: str | None = Field(None, min_length=1)
    sample_rate: float | None = Field(None, ge=0.0, le=1.0)
    judge_model: str | None = Field(None, min_length=1, max_length=100)
    judge_prompt_template: str | None = Field(None, min_length=1)
    enabled: bool | None = None


class VerificationRuleResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    match_jsonpath: str
    sample_rate: float
    judge_model: str
    judge_prompt_template: str
    enabled: bool

    model_config = {"from_attributes": True}


class VerificationRuleListResponse(BaseModel):
    rules: list[VerificationRuleResponse]
    total: int


class VerificationResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime
    trace_id: uuid.UUID
    judge_trace_id: uuid.UUID | None
    judge_model: str
    verdict: str
    confidence: float | None
    reasoning: str | None
    rule_id: uuid.UUID

    model_config = {"from_attributes": True}


class VerificationListResponse(BaseModel):
    verifications: list[VerificationResponse]
    next_cursor: str | None
    total_count: int
