"""Preserve verified historical display fields independently of extraction runs."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_display_recovery"
down_revision = "0015_media_content_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_display_profile",
        sa.Column("scope", sa.String(64), primary_key=True),
        sa.Column("topology_sha256", sa.String(64), primary_key=True),
        sa.Column(
            "reference_media_id",
            sa.Uuid(),
            sa.ForeignKey("media.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "bindings", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
    )
    op.create_table(
        "workflow_display_recovery",
        sa.Column(
            "media_id", sa.Uuid(), sa.ForeignKey("media.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("field_name", sa.String(40), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("original_sha256", sa.String(64), nullable=False),
        sa.Column("profile_sha256", sa.String(64), nullable=False),
        sa.Column("workflow_uuid", sa.String(36)),
        sa.Column("node_id", sa.String(128), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workflow_display_recovery")
    op.drop_table("workflow_display_profile")
