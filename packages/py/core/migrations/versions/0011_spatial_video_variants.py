"""Add imported media variants and canonical spatial playback preference.

Revision ID: 0011_spatial_video_variants
Revises: 0010_media_preferences
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_spatial_video_variants"
down_revision: str | None = "0010_media_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "media",
        "spatial_view_preferred",
        new_column_name="prefer_spatial_playback",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.false(),
    )
    op.add_column(
        "media",
        sa.Column(
            "spatial_available",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_media_spatial_available",
        "media",
        ["spatial_available"],
    )
    op.create_table(
        "media_variant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'staging'"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("original_extension", sa.String(length=32), nullable=True),
        sa.Column("managed_path", sa.String(length=1024), nullable=True),
        sa.Column("detected_format", sa.String(length=32), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
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
            "validation_data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("converter_name", sa.String(length=128), nullable=True),
        sa.Column("converter_version", sa.String(length=64), nullable=True),
        sa.Column("source_asset_sha256", sa.String(length=64), nullable=True),
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
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(NOT is_active) OR status = 'ready'",
            name="ck_media_variant_active_ready",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("managed_path"),
    )
    op.create_index("ix_media_variant_media_id", "media_variant", ["media_id"])
    op.create_index("ix_media_variant_status", "media_variant", ["status"])
    op.create_index(
        "ix_media_variant_idempotency_key_hash",
        "media_variant",
        ["idempotency_key_hash"],
        unique=True,
    )
    op.create_index(
        "ix_media_variant_sha256",
        "media_variant",
        ["sha256"],
        unique=True,
    )
    op.create_index(
        "ix_media_variant_media_role_status",
        "media_variant",
        ["media_id", "role", "status"],
    )
    op.create_index(
        "uq_media_variant_active_role",
        "media_variant",
        ["media_id", "role"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_media_variant_active_role",
        table_name="media_variant",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index("ix_media_variant_media_role_status", table_name="media_variant")
    op.drop_index("ix_media_variant_sha256", table_name="media_variant")
    op.drop_index("ix_media_variant_idempotency_key_hash", table_name="media_variant")
    op.drop_index("ix_media_variant_status", table_name="media_variant")
    op.drop_index("ix_media_variant_media_id", table_name="media_variant")
    op.drop_table("media_variant")
    op.drop_index("ix_media_spatial_available", table_name="media")
    op.drop_column("media", "spatial_available")
    op.alter_column(
        "media",
        "prefer_spatial_playback",
        new_column_name="spatial_view_preferred",
        existing_type=sa.Boolean(),
        existing_nullable=False,
        existing_server_default=sa.false(),
    )
