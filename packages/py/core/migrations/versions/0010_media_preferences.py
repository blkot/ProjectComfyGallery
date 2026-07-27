"""Add spatial-view and favorite media preferences.

Revision ID: 0010_media_preferences
Revises: 0009_media_evaluation_modules
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_media_preferences"
down_revision: str | None = "0009_media_evaluation_modules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "media",
        sa.Column(
            "spatial_view_preferred",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "media",
        sa.Column(
            "favorite",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("media", "favorite")
    op.drop_column("media", "spatial_view_preferred")
