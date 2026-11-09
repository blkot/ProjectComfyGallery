"""Persist human classifier decisions separately from model assessments.

Revision ID: 0024_media_safety_review
Revises: 0023_media_safety_assessment
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_media_safety_review"
down_revision: str | None = "0023_media_safety_assessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_safety_review",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.String(length=24), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["app_user.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("media_id", name="uq_media_safety_review_media"),
    )
    op.create_index(
        "ix_media_safety_review_rating",
        "media_safety_review",
        ["rating"],
    )
    op.create_index(
        "ix_media_safety_review_reviewer_user_id",
        "media_safety_review",
        ["reviewer_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_safety_review_reviewer_user_id", table_name="media_safety_review")
    op.drop_index("ix_media_safety_review_rating", table_name="media_safety_review")
    op.drop_table("media_safety_review")
