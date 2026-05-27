"""SQLAlchemy declarative models for the Sentinel database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all models."""

    pass


class Project(Base):
    """A project groups traces and is identified by an API key."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    api_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship
    traces: Mapped[list[Trace]] = relationship(
        "Trace", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name!r}>"


class Trace(Base):
    """A single logged LLM API call."""

    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    cost_usd: Mapped[float] = mapped_column(
        Numeric(12, 6), nullable=False, default=0.0
    )
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    request_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationship
    project: Mapped[Project] = relationship("Project", back_populates="traces")

    # Indexes
    __table_args__ = (
        Index("ix_traces_created_at", "created_at"),
        Index("ix_traces_project_id", "project_id"),
        Index("ix_traces_provider", "provider"),
        Index("ix_traces_model", "model"),
    )

    def __repr__(self) -> str:
        return f"<Trace {self.id} {self.provider}/{self.model}>"


class VerificationRule(Base):
    """Declarative rule deciding when a primary trace should be re-checked by a judge."""

    __tablename__ = "verification_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_jsonpath: Mapped[str] = mapped_column(Text, nullable=False)
    sample_rate: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False, default=0.0)
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    judge_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_verification_rules_project_id", "project_id"),)


class Verification(Base):
    """One judge evaluation of a primary call."""

    __tablename__ = "verifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="CASCADE"), nullable=False
    )
    judge_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True
    )
    judge_model: Mapped[str] = mapped_column(String(100), nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_rules.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        Index("ix_verifications_trace_id", "trace_id"),
        Index("ix_verifications_created_at", "created_at"),
    )


class RoutingPolicy(Base):
    """Declarative routing rule with ordered candidate models and fallback conditions."""

    __tablename__ = "routing_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_jsonpath: Mapped[str] = mapped_column(Text, nullable=False)
    candidates: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    fallback_on: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_routing_policies_project_id", "project_id"),)


class Eval(Base):
    """An eval suite (YAML-defined collection of test cases)."""

    __tablename__ = "evals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    yaml_source: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_evals_project_name"),
    )


class EvalRun(Base):
    """One execution of an eval suite."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    eval_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("evals.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    triggered_by: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    git_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_eval_runs_eval_started", "eval_id", "started_at"),
    )


class EvalCase(Base):
    """Per-case result within an eval run."""

    __tablename__ = "eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    case_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expected: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    actual: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assertion_log: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_eval_cases_run_passed", "run_id", "passed"),
    )
