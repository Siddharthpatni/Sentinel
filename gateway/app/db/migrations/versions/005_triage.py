"""005_triage: code_chunks (pgvector RAG), triage_executions, triage_approvals.

Revision ID: 005_triage
Revises: 004_auth
Create Date: 2026-07-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "005_triage"
down_revision = "004_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "code_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "file_path", "start_line", "end_line", name="uq_code_chunks_file_range"
        ),
    )
    op.create_index("ix_code_chunks_file_path", "code_chunks", ["file_path"])
    # ivfflat approximate-nearest-neighbor index for cosine distance search.
    # Requires ANALYZE / a non-trivial row count to be effective, but is safe
    # to create up front on an empty table.
    op.execute(
        "CREATE INDEX ix_code_chunks_embedding_cosine ON code_chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    op.create_table(
        "triage_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "trace_id",
            sa.Uuid(),
            sa.ForeignKey("traces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column(
            "current_node", sa.String(20), nullable=False, server_default="diagnostic"
        ),
        sa.Column("diagnosis", sa.JSON(), nullable=True),
        sa.Column("proposed_patch", sa.JSON(), nullable=True),
        sa.Column("patch_risk_tier", sa.String(10), nullable=True),
        sa.Column(
            "compliance_reasons", sa.JSON(), nullable=False, server_default="[]"
        ),
        sa.Column("pr_url", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_triage_executions_project_id", "triage_executions", ["project_id"]
    )
    op.create_index("ix_triage_executions_trace_id", "triage_executions", ["trace_id"])
    op.create_index("ix_triage_executions_status", "triage_executions", ["status"])

    op.create_table(
        "triage_approvals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "execution_id",
            sa.Uuid(),
            sa.ForeignKey("triage_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_triage_approvals_execution_id", "triage_approvals", ["execution_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_triage_approvals_execution_id", table_name="triage_approvals")
    op.drop_table("triage_approvals")
    op.drop_index("ix_triage_executions_status", table_name="triage_executions")
    op.drop_index("ix_triage_executions_trace_id", table_name="triage_executions")
    op.drop_index("ix_triage_executions_project_id", table_name="triage_executions")
    op.drop_table("triage_executions")
    op.execute("DROP INDEX IF EXISTS ix_code_chunks_embedding_cosine")
    op.drop_index("ix_code_chunks_file_path", table_name="code_chunks")
    op.drop_table("code_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")
