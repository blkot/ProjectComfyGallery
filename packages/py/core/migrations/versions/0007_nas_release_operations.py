"""Add portable export records for NAS release operations.

Revision ID: 0007_nas_release_operations
Revises: 0006_model_analytics
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_nas_release_operations"
down_revision: str | None = "0006_model_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column(
            "export_schema_version",
            sa.String(length=32),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "requested_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("artifact_path", sa.String(length=1024)),
        sa.Column("sha256", sa.String(length=64)),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column(
            "table_counts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_path"),
    )
    op.create_index("ix_export_run_status", "export_run", ["status"])
    op.create_index(
        "ix_export_run_created_by_user_id",
        "export_run",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_export_run_created",
        "export_run",
        ["created_by_user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_run_created", table_name="export_run")
    op.drop_index("ix_export_run_created_by_user_id", table_name="export_run")
    op.drop_index("ix_export_run_status", table_name="export_run")
    op.drop_table("export_run")
