"""Create immutable workflow evidence, generic graph, and extraction tables.

Revision ID: 0003_workflow_evidence
Revises: 0002_media_ingestion
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_workflow_evidence"
down_revision: str | None = "0002_media_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.create_table(
        "workflow_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("reader_name", sa.String(length=80), nullable=False),
        sa.Column("reader_version", sa.String(length=32), nullable=False),
        sa.Column("source_carrier", sa.String(length=80), nullable=False),
        sa.Column("evidence_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "raw_metadata",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("raw_api_prompt_text", sa.Text(), nullable=True),
        sa.Column("raw_visual_workflow_text", sa.Text(), nullable=True),
        sa.Column("api_prompt", _jsonb(), nullable=True),
        sa.Column("visual_workflow", _jsonb(), nullable=True),
        sa.Column("api_prompt_status", sa.String(length=32), nullable=False),
        sa.Column("visual_workflow_status", sa.String(length=32), nullable=False),
        sa.Column("parse_status", sa.String(length=32), nullable=False),
        sa.Column(
            "issue_details",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("graph_version", sa.String(length=32), nullable=True),
        sa.Column("api_node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("visual_node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("edge_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflow_snapshot_media_id",
        "workflow_snapshot",
        ["media_id"],
        unique=True,
    )
    op.create_index(
        "ix_workflow_snapshot_parse_status",
        "workflow_snapshot",
        ["parse_status"],
    )

    op.create_table(
        "workflow_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("representation", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("original_node_id", sa.String(length=128), nullable=False),
        sa.Column("class_type", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=True),
        sa.Column("module_hint", sa.String(length=512), nullable=True),
        sa.Column("mode", sa.Integer(), nullable=True),
        sa.Column(
            "raw_properties",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_widgets",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_inputs",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["workflow_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "representation",
            "original_node_id",
            name="uq_workflow_node_identity",
        ),
    )
    op.create_index("ix_workflow_node_class_type", "workflow_node", ["class_type"])
    op.create_index(
        "ix_workflow_node_representation",
        "workflow_node",
        ["representation"],
    )
    op.create_index("ix_workflow_node_snapshot_id", "workflow_node", ["snapshot_id"])

    op.create_table(
        "workflow_edge",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("representation", sa.String(length=32), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("original_link_id", sa.String(length=128), nullable=True),
        sa.Column("source_node_id", sa.String(length=128), nullable=False),
        sa.Column("source_output_index", sa.Integer(), nullable=True),
        sa.Column("destination_node_id", sa.String(length=128), nullable=False),
        sa.Column("destination_input_index", sa.Integer(), nullable=True),
        sa.Column("destination_input_name", sa.String(length=512), nullable=True),
        sa.Column("declared_type", sa.String(length=256), nullable=True),
        sa.Column("raw_link", _jsonb(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["workflow_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "representation",
            "ordinal",
            name="uq_workflow_edge_ordinal",
        ),
    )
    op.create_index(
        "ix_workflow_edge_representation",
        "workflow_edge",
        ["representation"],
    )
    op.create_index("ix_workflow_edge_snapshot_id", "workflow_edge", ["snapshot_id"])

    op.create_table(
        "workflow_value",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=False),
        sa.Column("locator", sa.String(length=512), nullable=False),
        sa.Column("input_name", sa.String(length=512), nullable=True),
        sa.Column("input_index", sa.Integer(), nullable=True),
        sa.Column("value_kind", sa.String(length=32), nullable=False),
        sa.Column("raw_value", _jsonb(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["node_id"], ["workflow_node.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("node_id", "locator", name="uq_workflow_value_locator"),
    )
    op.create_index("ix_workflow_value_input_name", "workflow_value", ["input_name"])
    op.create_index("ix_workflow_value_node_id", "workflow_value", ["node_id"])
    op.create_index("ix_workflow_value_value_kind", "workflow_value", ["value_kind"])

    op.create_table(
        "extraction_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("extractor_name", sa.String(length=80), nullable=False),
        sa.Column("extractor_version", sa.String(length=32), nullable=False),
        sa.Column("graph_version", sa.String(length=32), nullable=False),
        sa.Column("configuration_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "is_current",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("observation_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_details",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["workflow_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_extraction_run_snapshot_id", "extraction_run", ["snapshot_id"])
    op.create_index(
        "ix_extraction_run_snapshot_current",
        "extraction_run",
        ["snapshot_id", "is_current"],
    )
    op.create_index("ix_extraction_run_status", "extraction_run", ["status"])

    op.create_table(
        "semantic_observation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("observation_type", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("value", _jsonb(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "correction_state",
            sa.String(length=32),
            server_default="uncorrected",
            nullable=False,
        ),
        sa.Column(
            "evidence",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["workflow_node.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["extraction_run.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_semantic_observation_node_id",
        "semantic_observation",
        ["node_id"],
    )
    op.create_index(
        "ix_semantic_observation_observation_type",
        "semantic_observation",
        ["observation_type"],
    )
    op.create_index(
        "ix_semantic_observation_run_id",
        "semantic_observation",
        ["run_id"],
    )
    op.create_index(
        "ix_semantic_observation_type_role",
        "semantic_observation",
        ["observation_type", "role"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_semantic_observation_type_role",
        table_name="semantic_observation",
    )
    op.drop_index(
        "ix_semantic_observation_run_id",
        table_name="semantic_observation",
    )
    op.drop_index(
        "ix_semantic_observation_observation_type",
        table_name="semantic_observation",
    )
    op.drop_index(
        "ix_semantic_observation_node_id",
        table_name="semantic_observation",
    )
    op.drop_table("semantic_observation")
    op.drop_index("ix_extraction_run_status", table_name="extraction_run")
    op.drop_index(
        "ix_extraction_run_snapshot_current",
        table_name="extraction_run",
    )
    op.drop_index("ix_extraction_run_snapshot_id", table_name="extraction_run")
    op.drop_table("extraction_run")
    op.drop_index("ix_workflow_value_value_kind", table_name="workflow_value")
    op.drop_index("ix_workflow_value_node_id", table_name="workflow_value")
    op.drop_index("ix_workflow_value_input_name", table_name="workflow_value")
    op.drop_table("workflow_value")
    op.drop_index("ix_workflow_edge_snapshot_id", table_name="workflow_edge")
    op.drop_index("ix_workflow_edge_representation", table_name="workflow_edge")
    op.drop_table("workflow_edge")
    op.drop_index("ix_workflow_node_snapshot_id", table_name="workflow_node")
    op.drop_index("ix_workflow_node_representation", table_name="workflow_node")
    op.drop_index("ix_workflow_node_class_type", table_name="workflow_node")
    op.drop_table("workflow_node")
    op.drop_index("ix_workflow_snapshot_parse_status", table_name="workflow_snapshot")
    op.drop_index("ix_workflow_snapshot_media_id", table_name="workflow_snapshot")
    op.drop_table("workflow_snapshot")
