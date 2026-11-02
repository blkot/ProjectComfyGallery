"""Decouple prompt registry entries from workflow LoRA fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_prompt_registry_prompt_only"
down_revision: str | None = "0017_prompt_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("prompt_registry_entry", "lora_list")
    op.drop_column("prompt_registry_entry", "character_lora")


def downgrade() -> None:
    op.add_column(
        "prompt_registry_entry",
        sa.Column("character_lora", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "prompt_registry_entry",
        sa.Column(
            "lora_list",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )
