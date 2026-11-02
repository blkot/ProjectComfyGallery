"""Add the Gallery-side prompt registry keyed by source and index."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_prompt_registry"
down_revision: str | None = "0016_display_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_registry_entry",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=256), nullable=False),
        sa.Column("source_key", sa.String(length=256), nullable=False),
        sa.Column("entry_index", sa.String(length=128), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("negative_prompt", sa.Text(), nullable=True),
        sa.Column("character_lora", sa.String(length=1024), nullable=True),
        sa.Column(
            "lora_list",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "metadata",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("origin", sa.String(length=64), nullable=False, server_default="xanta-utils"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_key", "entry_index", name="uq_prompt_registry_source_index"),
    )
    op.create_index("ix_prompt_registry_source", "prompt_registry_entry", ["source_key"])
    op.create_index("ix_prompt_registry_index", "prompt_registry_entry", ["entry_index"])


def downgrade() -> None:
    op.drop_index("ix_prompt_registry_index", table_name="prompt_registry_entry")
    op.drop_index("ix_prompt_registry_source", table_name="prompt_registry_entry")
    op.drop_table("prompt_registry_entry")
