"""Add reversible model-reference alias identity groups.

Revision ID: 0008_reference_alias_groups
Revises: 0007_nas_release_operations
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_reference_alias_groups"
down_revision: str | None = "0007_nas_release_operations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_reference_group",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("canonical_key", sa.String(length=1024), nullable=False),
        sa.Column("display_name", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="confirmed",
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_reference_group_reference_type",
        "model_reference_group",
        ["reference_type"],
    )
    op.create_index(
        "ix_model_reference_group_status",
        "model_reference_group",
        ["status"],
    )
    op.create_index(
        "ix_model_reference_group_lookup",
        "model_reference_group",
        ["reference_type", "canonical_key", "status"],
    )
    op.add_column(
        "model_reference",
        sa.Column("identity_group_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_model_reference_identity_group_id",
        "model_reference",
        ["identity_group_id"],
    )
    op.create_foreign_key(
        "fk_model_reference_identity_group",
        "model_reference",
        "model_reference_group",
        ["identity_group_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_model_reference_identity_group",
        "model_reference",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_model_reference_identity_group_id",
        table_name="model_reference",
    )
    op.drop_column("model_reference", "identity_group_id")
    op.drop_index(
        "ix_model_reference_group_lookup",
        table_name="model_reference_group",
    )
    op.drop_index(
        "ix_model_reference_group_status",
        table_name="model_reference_group",
    )
    op.drop_index(
        "ix_model_reference_group_reference_type",
        table_name="model_reference_group",
    )
    op.drop_table("model_reference_group")
