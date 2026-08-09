"""Add captured workflow input references and deduplicated assets.

Revision ID: 0012_workflow_input_media
Revises: 0011_spatial_video_variants
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_workflow_input_media"
down_revision: str | None = "0011_spatial_video_variants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflow_input_asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("detected_format", sa.String(length=32), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("original_extension", sa.String(length=32), nullable=True),
        sa.Column("managed_path", sa.String(length=1024), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("frame_rate", sa.Float(), nullable=True),
        sa.Column("container", sa.String(length=64), nullable=True),
        sa.Column("video_codec", sa.String(length=64), nullable=True),
        sa.Column("audio_codec", sa.String(length=64), nullable=True),
        sa.Column(
            "probe_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("managed_path"),
    )
    op.create_index(
        "ix_workflow_input_asset_sha256",
        "workflow_input_asset",
        ["sha256"],
        unique=True,
    )
    op.create_index(
        "ix_workflow_input_asset_kind",
        "workflow_input_asset",
        ["kind"],
    )

    op.create_table(
        "workflow_input_reference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("input_asset_id", sa.Uuid(), nullable=True),
        sa.Column("representation", sa.String(length=32), nullable=False),
        sa.Column("original_node_id", sa.String(length=128), nullable=False),
        sa.Column("class_type", sa.String(length=512), nullable=False),
        sa.Column("locator", sa.String(length=512), nullable=False),
        sa.Column("input_name", sa.String(length=512), nullable=True),
        sa.Column("media_kind_hint", sa.String(length=16), nullable=True),
        sa.Column("source_filename", sa.String(length=1024), nullable=False),
        sa.Column("source_subfolder", sa.String(length=2048), nullable=True),
        sa.Column(
            "source_type",
            sa.String(length=32),
            server_default=sa.text("'input'"),
            nullable=False,
        ),
        sa.Column("raw_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column(
            "resolution_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["input_asset_id"],
            ["workflow_input_asset.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["node_id"], ["workflow_node.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["workflow_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "representation",
            "original_node_id",
            "locator",
            name="uq_workflow_input_reference_identity",
        ),
    )
    op.create_index(
        "ix_workflow_input_reference_snapshot_id",
        "workflow_input_reference",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_workflow_input_reference_node_id",
        "workflow_input_reference",
        ["node_id"],
    )
    op.create_index(
        "ix_workflow_input_reference_input_asset_id",
        "workflow_input_reference",
        ["input_asset_id"],
    )
    op.create_index(
        "ix_workflow_input_reference_status",
        "workflow_input_reference",
        ["status"],
    )
    op.create_index(
        "ix_workflow_input_reference_snapshot_status",
        "workflow_input_reference",
        ["snapshot_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workflow_input_reference_snapshot_status",
        table_name="workflow_input_reference",
    )
    op.drop_index("ix_workflow_input_reference_status", table_name="workflow_input_reference")
    op.drop_index(
        "ix_workflow_input_reference_input_asset_id",
        table_name="workflow_input_reference",
    )
    op.drop_index("ix_workflow_input_reference_node_id", table_name="workflow_input_reference")
    op.drop_index(
        "ix_workflow_input_reference_snapshot_id",
        table_name="workflow_input_reference",
    )
    op.drop_table("workflow_input_reference")
    op.drop_index("ix_workflow_input_asset_kind", table_name="workflow_input_asset")
    op.drop_index("ix_workflow_input_asset_sha256", table_name="workflow_input_asset")
    op.drop_table("workflow_input_asset")
