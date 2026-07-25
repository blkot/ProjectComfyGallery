"""Add per-media optional evaluation module settings.

Revision ID: 0009_media_evaluation_modules
Revises: 0008_reference_alias_groups
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_media_evaluation_modules"
down_revision: str | None = "0008_reference_alias_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_evaluation_module",
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_id", "module"),
    )
    op.create_index(
        "ix_media_evaluation_module_enabled",
        "media_evaluation_module",
        ["module", "enabled"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO media_evaluation_module (media_id, module, enabled)
            SELECT DISTINCT evaluation.media_id, evaluation_template.module, true
            FROM evaluation
            JOIN evaluation_template
              ON evaluation_template.id = evaluation.template_id
            WHERE evaluation_template.module <> 'core'
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_evaluation_module_enabled",
        table_name="media_evaluation_module",
    )
    op.drop_table("media_evaluation_module")
