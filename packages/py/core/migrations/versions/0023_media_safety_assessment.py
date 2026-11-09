"""Persist the latest NSFW model suggestion independently from human ratings.

Revision ID: 0023_media_safety_assessment
Revises: 0022_media_rating_default_sfw
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_media_safety_assessment"
down_revision: str | None = "0022_media_rating_default_sfw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_safety_assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_revision", sa.String(length=128), nullable=False),
        sa.Column(
            "inference_backend",
            sa.String(length=24),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("suggested_rating", sa.String(length=24), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("margin", sa.Float(), nullable=True),
        sa.Column(
            "scores",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "needs_review",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column(
            "nudity_detector_status",
            sa.String(length=24),
            server_default="disabled",
            nullable=False,
        ),
        sa.Column(
            "nudity_detector_mode",
            sa.String(length=24),
            server_default="disabled",
            nullable=False,
        ),
        sa.Column(
            "nudity_detected",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("nudity_model_id", sa.String(length=128), nullable=True),
        sa.Column("nudity_model_revision", sa.String(length=128), nullable=True),
        sa.Column(
            "nudity_detections",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["job.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_id", name="uq_media_safety_assessment_media"),
    )
    op.create_index(
        "ix_media_safety_assessment_status",
        "media_safety_assessment",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_safety_assessment_status",
        table_name="media_safety_assessment",
    )
    op.drop_table("media_safety_assessment")
