"""Add an optional SFW/NSFW content rating to media records.

Revision ID: 0015_media_content_rating
Revises: 0014_event_driven_mss
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_media_content_rating"
down_revision: str | None = "0014_event_driven_mss"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("media", sa.Column("content_rating", sa.String(length=16), nullable=True))
    op.create_index("ix_media_content_rating", "media", ["content_rating"])


def downgrade() -> None:
    op.drop_index("ix_media_content_rating", table_name="media")
    op.drop_column("media", "content_rating")
