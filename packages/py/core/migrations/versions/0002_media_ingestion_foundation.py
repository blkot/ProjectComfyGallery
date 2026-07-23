"""Create media identity, source inventory, upload, derivative, and job tables.

Revision ID: 0002_media_ingestion
Revises: 0001_auth_foundation
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_media_ingestion"
down_revision: str | None = "0001_auth_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="processing", nullable=False),
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
        sa.Column("warning_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_kind", "media", ["kind"], unique=False)
    op.create_index("ix_media_status", "media", ["status"], unique=False)

    op.create_table(
        "source_root",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )

    op.create_table(
        "upload_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="receiving", nullable=False),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("queued_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_upload_batch_status", "upload_batch", ["status"], unique=False)

    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("queue", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress_current", sa.Integer(), server_default="0", nullable=False),
        sa.Column("progress_total", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "cancel_requested",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details",
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
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_kind", "job", ["kind"], unique=False)
    op.create_index("ix_job_resource", "job", ["resource_type", "resource_id"], unique=False)
    op.create_index("ix_job_status", "job", ["status"], unique=False)

    op.create_table(
        "media_asset",
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("original_extension", sa.String(length=32), nullable=True),
        sa.Column("managed_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "stored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_id"),
        sa.UniqueConstraint("managed_path"),
    )
    op.create_index("ix_media_asset_sha256", "media_asset", ["sha256"], unique=True)

    op.create_table(
        "derivative",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("recipe_version", sa.String(length=32), nullable=False),
        sa.Column("managed_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("container", sa.String(length=64), nullable=True),
        sa.Column("codec", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("managed_path"),
        sa.UniqueConstraint(
            "media_id",
            "kind",
            "recipe_version",
            name="uq_derivative_media_kind_recipe",
        ),
    )
    op.create_index("ix_derivative_kind", "derivative", ["kind"], unique=False)
    op.create_index("ix_derivative_media_id", "derivative", ["media_id"], unique=False)

    op.create_table(
        "scan_batch",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_root_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("discovered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("missing_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["source_root_id"], ["source_root.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scan_batch_source_root_id", "scan_batch", ["source_root_id"])
    op.create_index("ix_scan_batch_status", "scan_batch", ["status"])

    op.create_table(
        "source_occurrence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_root_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=True),
        sa.Column("relative_path", sa.String(length=2048), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("mtime_ns", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="present", nullable=False),
        sa.Column("first_seen_scan_id", sa.Uuid(), nullable=False),
        sa.Column("last_seen_scan_id", sa.Uuid(), nullable=False),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
            ["first_seen_scan_id"],
            ["scan_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["last_seen_scan_id"],
            ["scan_batch.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["source_root_id"],
            ["source_root.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_occurrence_current_path",
        "source_occurrence",
        ["source_root_id", "relative_path", "superseded_at"],
    )
    op.create_index(
        "ix_source_occurrence_last_seen_scan_id", "source_occurrence", ["last_seen_scan_id"]
    )
    op.create_index("ix_source_occurrence_media_id", "source_occurrence", ["media_id"])
    op.create_index("ix_source_occurrence_sha256", "source_occurrence", ["sha256"])
    op.create_index("ix_source_occurrence_source_root_id", "source_occurrence", ["source_root_id"])
    op.create_index("ix_source_occurrence_status", "source_occurrence", ["status"])

    op.create_table(
        "upload_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("batch_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=True),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("staging_path", sa.String(length=1024), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="receiving", nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["upload_batch.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staging_path"),
    )
    op.create_index("ix_upload_item_batch_id", "upload_item", ["batch_id"])
    op.create_index("ix_upload_item_media_id", "upload_item", ["media_id"])
    op.create_index("ix_upload_item_status", "upload_item", ["status"])

    op.create_table(
        "job_stage_attempt",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("job_attempt", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id",
            "stage",
            "job_attempt",
            name="uq_job_stage_attempt",
        ),
    )
    op.create_index("ix_job_stage_attempt_job_id", "job_stage_attempt", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_job_stage_attempt_job_id", table_name="job_stage_attempt")
    op.drop_table("job_stage_attempt")
    op.drop_index("ix_upload_item_status", table_name="upload_item")
    op.drop_index("ix_upload_item_media_id", table_name="upload_item")
    op.drop_index("ix_upload_item_batch_id", table_name="upload_item")
    op.drop_table("upload_item")
    op.drop_index("ix_source_occurrence_status", table_name="source_occurrence")
    op.drop_index("ix_source_occurrence_source_root_id", table_name="source_occurrence")
    op.drop_index("ix_source_occurrence_sha256", table_name="source_occurrence")
    op.drop_index("ix_source_occurrence_media_id", table_name="source_occurrence")
    op.drop_index("ix_source_occurrence_last_seen_scan_id", table_name="source_occurrence")
    op.drop_index("ix_source_occurrence_current_path", table_name="source_occurrence")
    op.drop_table("source_occurrence")
    op.drop_index("ix_scan_batch_status", table_name="scan_batch")
    op.drop_index("ix_scan_batch_source_root_id", table_name="scan_batch")
    op.drop_table("scan_batch")
    op.drop_index("ix_derivative_media_id", table_name="derivative")
    op.drop_index("ix_derivative_kind", table_name="derivative")
    op.drop_table("derivative")
    op.drop_index("ix_media_asset_sha256", table_name="media_asset")
    op.drop_table("media_asset")
    op.drop_index("ix_job_status", table_name="job")
    op.drop_index("ix_job_resource", table_name="job")
    op.drop_index("ix_job_kind", table_name="job")
    op.drop_table("job")
    op.drop_index("ix_upload_batch_status", table_name="upload_batch")
    op.drop_table("upload_batch")
    op.drop_table("source_root")
    op.drop_index("ix_media_status", table_name="media")
    op.drop_index("ix_media_kind", table_name="media")
    op.drop_table("media")
