"""Materialize the character LoRA display value for Prompt Registry filters."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_prompt_index_character_lora"
down_revision: str | None = "0020_prompt_registry_index_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media_prompt_index",
        sa.Column("character_lora", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("media_prompt_index", "character_lora")
