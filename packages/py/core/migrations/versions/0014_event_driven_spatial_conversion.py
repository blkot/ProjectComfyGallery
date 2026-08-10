"""Add bounded reconciliation state for event-driven MSS orchestration.

Revision ID: 0014_event_driven_mss
Revises: 0013_spatial_conversion_runs
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_event_driven_mss"
down_revision: str | None = "0013_spatial_conversion_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "spatial_conversion_run",
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "spatial_conversion_run",
        sa.Column("next_reconciliation_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_spatial_conversion_run_next_reconciliation_at",
        "spatial_conversion_run",
        ["next_reconciliation_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_spatial_conversion_run_next_reconciliation_at", table_name="spatial_conversion_run"
    )
    op.drop_column("spatial_conversion_run", "next_reconciliation_at")
    op.drop_column("spatial_conversion_run", "last_reconciled_at")
