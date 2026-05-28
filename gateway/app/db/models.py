"""SQLAlchemy declarative models for the Sentinel database."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Portable JSON: real JSONB on Postgres (with all of its querying / indexing
# benefits), generic JSON on SQLite so the in-memory test DB can still
# `create_all`. We don't rely on JSONB-specific operators in the ORM layer,
# so the variant is transparent at the Python level.
JSONType = JSON().with_variant(JSONB(), "postgresql")


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
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("orgs.id", ondelete="SET NULL"), nullable=True, index=True
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
    request_body: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    response_body: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
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
        Index("ix_traces_risk_tier", "risk_tier"),
        Index("ix_traces_session_id", "session_id"),
    )

    def __repr__(self) -> str:
        return f"<Trace {self.id} {self.provider}/{self.model}>"


class Span(Base):
    """One node in a trace tree.

    Spans nest via ``parent_span_id`` (self-referential, null = root). A
    trace can carry many spans — typically one root agent span with LLM
    and tool spans beneath. Stored flat; the dashboard rebuilds the tree
    client-side from ``parent_span_id``.
    """

    __tablename__ = "spans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="CASCADE"), nullable=False
    )
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("spans.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # "agent" | "llm" | "tool" | "chain" | "retriever" | "custom"
    span_type: Mapped[str] = mapped_column(String(32), nullable=False, default="custom")
    start_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_ts: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # "ok" | "error"
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    attributes: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_spans_trace_id", "trace_id"),
        Index("ix_spans_parent", "parent_span_id"),
    )

    def __repr__(self) -> str:
        return f"<Span {self.id} {self.span_type}:{self.name}>"


class Dataset(Base):
    """Named collection of input examples for replay, eval, or playground use.

    Holds many ``DatasetItem`` rows. Items typically capture the full
    request body (messages, model, etc.) and optionally an expected
    output so they can be re-run through the gateway and compared.
    """

    __tablename__ = "datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_datasets_project_name"),
        Index("ix_datasets_project_id", "project_id"),
    )


class DatasetItem(Base):
    """One input example inside a Dataset.

    ``input`` is the wire-shape request the playground/eval will send
    (e.g. ``{"messages": [...], "model": "gpt-4o-mini"}``).
    ``expected_output`` is optional ground truth for assertion-style
    evals. ``source_trace_id`` records the trace this row was captured
    from, so the dashboard can link back.
    """

    __tablename__ = "dataset_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False
    )
    input: Mapped[dict] = mapped_column(JSONType, nullable=False)
    expected_output: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    item_metadata: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    source_trace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_dataset_items_dataset_id", "dataset_id"),
    )


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
    candidates: Mapped[list[dict]] = mapped_column(JSONType, nullable=False)
    fallback_on: Mapped[dict] = mapped_column(JSONType, nullable=False)
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
    input: Mapped[dict] = mapped_column(JSONType, nullable=False)
    expected: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    actual: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assertion_log: Mapped[list[dict]] = mapped_column(JSONType, nullable=False, default=list)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_eval_cases_run_passed", "run_id", "passed"),
    )


class AuditClassifier(Base):
    """Declarative rule mapping a request shape to an EU-AI-Act risk tier."""

    __tablename__ = "audit_classifiers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    match_jsonpath: Mapped[str] = mapped_column(Text, nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_audit_classifiers_project_id", "project_id"),)


class AuditLogEntry(Base):
    """Append-only audit ledger. Each entry's hash chains to its predecessor.

    The ledger is intentionally separate from `traces` so it can be wiped or
    archived independently and so deletes on `traces` (cascade from project
    deletion) leave the audit trail intact.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    trace_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    risk_tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entry_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    __table_args__ = (
        Index("ix_audit_log_project_seq", "project_id", "sequence"),
        Index("ix_audit_log_created_at", "created_at"),
        UniqueConstraint("project_id", "sequence", name="uq_audit_log_project_sequence"),
    )


class Alert(Base):
    """Threshold alert configured per project.

    Alerts are evaluated on demand (`POST /api/alerts/{id}/check`) — no
    scheduler runs them automatically. Sentinel records the result on the
    alert row so the dashboard can show a red dot when something tripped.
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # one of: "cost_per_hour_usd", "error_rate_pct", "latency_p95_ms"
    metric: Mapped[str] = mapped_column(String(40), nullable=False)
    # comparison: "gt", "lt"
    comparator: Mapped[str] = mapped_column(String(4), nullable=False, default="gt")
    threshold: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    # rolling lookback window in minutes
    window_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    last_triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_alerts_project_id", "project_id"),)


class TraceAnnotation(Base):
    """Human feedback on a trace (LangSmith-style thumbs up/down + comment).

    Multiple annotations per trace allowed (different reviewers, different
    dimensions). The composite index supports the dashboard "show me all
    annotations for this trace" lookup.
    """

    __tablename__ = "trace_annotations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("traces.id", ondelete="CASCADE"), nullable=False
    )
    # "thumbs_up" | "thumbs_down" | "neutral"
    rating: Mapped[str] = mapped_column(String(20), nullable=False)
    # free-form dimension label so teams can have multiple rating axes
    # (e.g. "accuracy", "helpfulness"). Defaults to "overall".
    dimension: Mapped[str] = mapped_column(String(40), nullable=False, default="overall")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (Index("ix_trace_annotations_trace_id", "trace_id"),)


class Session(Base):
    """A conversation thread — group multiple traces into one user session.

    LangSmith calls these "threads". A client tags requests with
    ``_sentinel.session_id`` and Sentinel persists the mapping, so the
    dashboard can show the entire conversation chronologically.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # free-form key supplied by the caller (string ID from their app)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONType, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "external_id", name="uq_sessions_project_extid"),
        Index("ix_sessions_project_last_seen", "project_id", "last_seen_at"),
    )


class ProviderCredential(Base):
    """Project-scoped, encrypted LLM provider API keys (BYOK).

    Each row stores one credential for one provider, encrypted with Fernet
    using the gateway's master key. The plaintext key never leaves
    ``keyvault.encrypt`` / ``keyvault.decrypt`` — the rest of the system
    works with the ciphertext or a short fingerprint suitable for display.
    """

    __tablename__ = "provider_credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    encrypted_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id", "provider", "label", name="uq_credentials_project_provider_label"
        ),
        Index("ix_credentials_project_provider", "project_id", "provider"),
    )


class Org(Base):
    """A billing/ownership boundary that groups projects and members."""

    __tablename__ = "orgs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class User(Base):
    """A human account. Belongs to one or more orgs via OrgMember."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrgMember(Base):
    """Membership of a User in an Org, with a role."""

    __tablename__ = "org_members"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("orgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
    )


class ApiKey(Base):
    """Scoped ingest/admin key for a project.

    The plaintext key is shown to the user exactly once at creation. Only
    the SHA-256 hash is stored; ``key_prefix`` (first 8 chars) is kept for
    display/disambiguation.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("project_id", "label", name="uq_api_keys_project_label"),
    )
