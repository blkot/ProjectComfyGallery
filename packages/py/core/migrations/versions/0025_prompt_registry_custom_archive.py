"""Support reversible archival of custom prompt registry entries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_prompt_registry_archive"
down_revision: str | None = "0024_media_safety_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prompt_registry_entry",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prompt_registry_entry", "archived_at")
