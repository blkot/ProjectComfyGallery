"""Materialize trusted Prompt ID resolution for indexed lookups."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_media_prompt_index"
down_revision: str | None = "0018_prompt_registry_prompt_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_prompt_index",
        sa.Column(
            "media_id",
            sa.Uuid(),
            sa.ForeignKey("media.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_key", sa.String(length=256), nullable=True),
        sa.Column("entry_index", sa.String(length=128), nullable=True),
        sa.Column("index_value", sa.Integer(), nullable=True),
        sa.Column("prompt_id", sa.String(length=512), nullable=True),
        sa.Column("evidence_source", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("original_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_media_prompt_index_lookup",
        "media_prompt_index",
        ["source_key", "index_value"],
    )


def downgrade() -> None:
    op.drop_index("ix_media_prompt_index_lookup", table_name="media_prompt_index")
    op.drop_table("media_prompt_index")
