"""Add canonical numeric keys for prompt registry entries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_prompt_registry_index_key"
down_revision: str | None = "0019_media_prompt_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prompt_registry_entry",
        sa.Column("entry_index_key", sa.String(length=128), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, entry_index FROM prompt_registry_entry")).all()
    for row in rows:
        index = str(row.entry_index)
        connection.execute(
            sa.text(
                "UPDATE prompt_registry_entry SET entry_index_key = :entry_index_key WHERE id = :id"
            ),
            {
                "id": row.id,
                "entry_index_key": index.lstrip("0") or "0",
            },
        )

    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("prompt_registry_entry") as batch_op:
            batch_op.alter_column(
                "entry_index_key",
                existing_type=sa.String(length=128),
                nullable=False,
            )
    else:
        op.alter_column(
            "prompt_registry_entry",
            "entry_index_key",
            existing_type=sa.String(length=128),
            nullable=False,
        )

    op.create_index(
        "ix_prompt_registry_materialization",
        "prompt_registry_entry",
        ["source_key", "entry_index_key"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prompt_registry_materialization",
        table_name="prompt_registry_entry",
    )
    op.drop_column("prompt_registry_entry", "entry_index_key")
