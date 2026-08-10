"""Add durable external spatial conversion runs.

Revision ID: 0013_spatial_conversion_runs
Revises: 0012_workflow_input_media
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013_spatial_conversion_runs"
down_revision: str | None = "0012_workflow_input_media"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spatial_conversion_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column(
            "requested_options",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("mss_batch_id", sa.String(length=128), nullable=True),
        sa.Column("mss_status_url", sa.String(length=1024), nullable=True),
        sa.Column("queue_position", sa.Integer(), nullable=True),
        sa.Column("mss_file_status", sa.String(length=64), nullable=True),
        sa.Column("publish_status", sa.String(length=64), nullable=True),
        sa.Column("previous_variant_id", sa.Uuid(), nullable=True),
        sa.Column("gallery_media_id", sa.Uuid(), nullable=True),
        sa.Column("gallery_variant_id", sa.Uuid(), nullable=True),
        sa.Column(
            "response_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_spatial_conversion_run_media_id",
        "spatial_conversion_run",
        ["media_id"],
    )
    op.create_index(
        "ix_spatial_conversion_run_created_by_user_id",
        "spatial_conversion_run",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_spatial_conversion_run_status",
        "spatial_conversion_run",
        ["status"],
    )
    op.create_index(
        "ix_spatial_conversion_run_mss_batch_id",
        "spatial_conversion_run",
        ["mss_batch_id"],
    )
    op.create_index(
        "ix_spatial_conversion_run_media_created",
        "spatial_conversion_run",
        ["media_id", "created_at"],
    )
    op.create_index(
        "uq_spatial_conversion_run_active_media",
        "spatial_conversion_run",
        ["media_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'submitting', 'processing')"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_spatial_conversion_run_active_media",
        table_name="spatial_conversion_run",
    )
    op.drop_index(
        "ix_spatial_conversion_run_media_created",
        table_name="spatial_conversion_run",
    )
    op.drop_index(
        "ix_spatial_conversion_run_mss_batch_id",
        table_name="spatial_conversion_run",
    )
    op.drop_index("ix_spatial_conversion_run_status", table_name="spatial_conversion_run")
    op.drop_index(
        "ix_spatial_conversion_run_created_by_user_id",
        table_name="spatial_conversion_run",
    )
    op.drop_index("ix_spatial_conversion_run_media_id", table_name="spatial_conversion_run")
    op.drop_table("spatial_conversion_run")
