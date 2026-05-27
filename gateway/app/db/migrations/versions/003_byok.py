"""003_byok: per-project provider credentials (Fernet-encrypted).

Revision ID: 003_byok
Revises:
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_byok"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("encrypted_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_fingerprint", sa.String(32), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "project_id",
            "provider",
            "label",
            name="uq_credentials_project_provider_label",
        ),
    )
    op.create_index(
        "ix_credentials_project_provider",
        "provider_credentials",
        ["project_id", "provider"],
    )
    op.create_index(
        "ix_provider_credentials_project_id", "provider_credentials", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_provider_credentials_project_id", table_name="provider_credentials")
    op.drop_index("ix_credentials_project_provider", table_name="provider_credentials")
    op.drop_table("provider_credentials")
