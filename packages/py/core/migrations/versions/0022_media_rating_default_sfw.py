"""Make SFW the persisted default content rating for every media record.

Revision ID: 0022_media_rating_default_sfw
Revises: 0021_prompt_index_character_lora
Create Date: 2026-11-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_media_rating_default_sfw"
down_revision: str | None = "0021_prompt_index_character_lora"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("UPDATE media SET content_rating = 'sfw' WHERE content_rating IS NULL")
    )

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("media") as batch_op:
            batch_op.alter_column(
                "content_rating",
                existing_type=sa.String(length=16),
                nullable=False,
                server_default="sfw",
            )
    else:
        op.alter_column(
            "media",
            "content_rating",
            existing_type=sa.String(length=16),
            existing_nullable=True,
            nullable=False,
            server_default="sfw",
        )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("media") as batch_op:
            batch_op.alter_column(
                "content_rating",
                existing_type=sa.String(length=16),
                nullable=True,
                server_default=None,
            )
    else:
        op.alter_column(
            "media",
            "content_rating",
            existing_type=sa.String(length=16),
            existing_nullable=False,
            nullable=True,
            server_default=None,
        )
