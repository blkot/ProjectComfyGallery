"""Create offline node and model registries.

Revision ID: 0004_node_model_registries
Revises: 0003_workflow_evidence
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_node_model_registries"
down_revision: str | None = "0003_workflow_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
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
    )


def upgrade() -> None:
    op.create_table(
        "node_schema_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("comfyui_version", sa.String(length=128), nullable=True),
        sa.Column("object_info_sha256", sa.String(length=64), nullable=False),
        sa.Column("raw_object_info", _jsonb(), nullable=False),
        sa.Column("definition_count", sa.Integer(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_node_schema_snapshot_object_info_sha256",
        "node_schema_snapshot",
        ["object_info_sha256"],
        unique=True,
    )

    op.create_table(
        "registry_sync_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("registry_kind", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column(
            "requested_options",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("current_stage", sa.String(length=80), nullable=True),
        sa.Column(
            "stage_status",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "counts",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_versions",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("node_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["node_snapshot_id"],
            ["node_schema_snapshot.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registry_sync_run_registry_kind",
        "registry_sync_run",
        ["registry_kind"],
    )
    op.create_index(
        "ix_registry_sync_run_status",
        "registry_sync_run",
        ["status"],
    )
    op.create_index(
        "ix_registry_sync_run_node_snapshot_id",
        "registry_sync_run",
        ["node_snapshot_id"],
    )

    op.create_table(
        "node_definition",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("class_type", sa.String(length=512), nullable=False),
        sa.Column(
            "python_module",
            sa.String(length=512),
            server_default="",
            nullable=False,
        ),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=1024), nullable=True),
        sa.Column("category", sa.String(length=1024), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "input_schema",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "output_schema",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_definition",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_present",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "mapping_state",
            sa.String(length=32),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column(
            "workflow_occurrence_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"],
            ["node_schema_snapshot.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "class_type",
            "python_module",
            "schema_fingerprint",
            name="uq_node_definition_variant",
        ),
    )
    op.create_index(
        "ix_node_definition_source_snapshot_id",
        "node_definition",
        ["source_snapshot_id"],
    )
    op.create_index("ix_node_definition_class_type", "node_definition", ["class_type"])
    op.create_index(
        "ix_node_definition_schema_fingerprint",
        "node_definition",
        ["schema_fingerprint"],
    )
    op.create_index("ix_node_definition_is_present", "node_definition", ["is_present"])
    op.create_index("ix_node_definition_mapping_state", "node_definition", ["mapping_state"])
    op.create_index(
        "ix_node_definition_review",
        "node_definition",
        ["mapping_state", "is_present"],
    )

    op.create_table(
        "node_semantic_mapping",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_definition_id", sa.Uuid(), nullable=False),
        sa.Column("locator", sa.String(length=512), nullable=False),
        sa.Column("input_name", sa.String(length=512), nullable=True),
        sa.Column("input_index", sa.Integer(), nullable=True),
        sa.Column("semantic_type", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "state",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
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
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["node_definition_id"],
            ["node_definition.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "node_definition_id",
            "locator",
            name="uq_node_semantic_mapping_locator",
        ),
    )
    op.create_index(
        "ix_node_semantic_mapping_node_definition_id",
        "node_semantic_mapping",
        ["node_definition_id"],
    )
    op.create_index(
        "ix_node_semantic_mapping_semantic_type",
        "node_semantic_mapping",
        ["semantic_type"],
    )
    op.create_index(
        "ix_node_semantic_mapping_state",
        "node_semantic_mapping",
        ["state"],
    )

    op.add_column("workflow_node", sa.Column("node_definition_id", sa.Uuid(), nullable=True))
    op.add_column(
        "workflow_node",
        sa.Column(
            "definition_match_state",
            sa.String(length=32),
            server_default="unresolved",
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_node",
        sa.Column("definition_confidence", sa.Float(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_node_node_definition",
        "workflow_node",
        "node_definition",
        ["node_definition_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_workflow_node_node_definition_id",
        "workflow_node",
        ["node_definition_id"],
    )
    op.create_index(
        "ix_workflow_node_definition_match_state",
        "workflow_node",
        ["definition_match_state"],
    )

    op.create_table(
        "model_artifact",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=1024), nullable=False),
        sa.Column("file_name", sa.String(length=1024), nullable=True),
        sa.Column("file_path", sa.String(length=2048), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=64), server_default="local", nullable=False),
        sa.Column("provider_model_id", sa.String(length=128), nullable=True),
        sa.Column("provider_version_id", sa.String(length=128), nullable=True),
        sa.Column("provider_url", sa.Text(), nullable=True),
        sa.Column("identity_state", sa.String(length=32), nullable=False),
        sa.Column("availability", sa.String(length=32), nullable=False),
        sa.Column("enrichment_state", sa.String(length=32), nullable=False),
        sa.Column("architecture_family", sa.String(length=256), nullable=True),
        sa.Column("lineage", sa.String(length=256), nullable=True),
        sa.Column("variant", sa.String(length=256), nullable=True),
        sa.Column("precision", sa.String(length=64), nullable=True),
        sa.Column("quantization", sa.String(length=64), nullable=True),
        sa.Column(
            "raw_inventory",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "raw_provider_metadata",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "manual_overrides",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sha256", name="uq_model_artifact_sha256"),
    )
    op.create_index("ix_model_artifact_artifact_type", "model_artifact", ["artifact_type"])
    op.create_index("ix_model_artifact_file_name", "model_artifact", ["file_name"])
    op.create_index("ix_model_artifact_sha256", "model_artifact", ["sha256"])
    op.create_index("ix_model_artifact_provider_model_id", "model_artifact", ["provider_model_id"])
    op.create_index(
        "ix_model_artifact_provider_version_id",
        "model_artifact",
        ["provider_version_id"],
    )
    op.create_index("ix_model_artifact_identity_state", "model_artifact", ["identity_state"])
    op.create_index("ix_model_artifact_availability", "model_artifact", ["availability"])
    op.create_index(
        "ix_model_artifact_enrichment_state",
        "model_artifact",
        ["enrichment_state"],
    )
    op.create_index(
        "ix_model_artifact_architecture_family",
        "model_artifact",
        ["architecture_family"],
    )
    op.create_index("ix_model_artifact_lineage", "model_artifact", ["lineage"])
    op.create_index(
        "ix_model_artifact_registry_state",
        "model_artifact",
        ["artifact_type", "availability"],
    )

    op.create_table(
        "model_reference",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("reference_type", sa.String(length=64), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=False),
        sa.Column("availability", sa.String(length=32), nullable=False),
        sa.Column("resolution_state", sa.String(length=32), nullable=False),
        sa.Column("match_method", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "candidate_artifact_ids",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "manual_override",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_artifact.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_type",
            "normalized_value",
            name="uq_model_reference_value",
        ),
    )
    op.create_index("ix_model_reference_artifact_id", "model_reference", ["artifact_id"])
    op.create_index("ix_model_reference_reference_type", "model_reference", ["reference_type"])
    op.create_index("ix_model_reference_availability", "model_reference", ["availability"])
    op.create_index("ix_model_reference_resolution_state", "model_reference", ["resolution_state"])
    op.create_index(
        "ix_model_reference_resolution",
        "model_reference",
        ["resolution_state", "availability"],
    )

    op.create_table(
        "model_usage",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.Uuid(), nullable=True),
        sa.Column("observation_id", sa.Uuid(), nullable=True),
        sa.Column("model_reference_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("observation_type", sa.String(length=80), nullable=False),
        sa.Column("pipeline_pattern", sa.String(length=80), nullable=False),
        sa.Column("slot", sa.String(length=80), nullable=False),
        sa.Column("usage_order", sa.Integer(), nullable=False),
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
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_artifact.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_reference_id"],
            ["model_reference.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["workflow_node.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["semantic_observation.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["workflow_snapshot.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id",
            "node_id",
            "model_reference_id",
            "observation_type",
            name="uq_model_usage_occurrence",
        ),
    )
    op.create_index("ix_model_usage_snapshot_id", "model_usage", ["snapshot_id"])
    op.create_index("ix_model_usage_node_id", "model_usage", ["node_id"])
    op.create_index("ix_model_usage_observation_id", "model_usage", ["observation_id"])
    op.create_index("ix_model_usage_model_reference_id", "model_usage", ["model_reference_id"])
    op.create_index("ix_model_usage_artifact_id", "model_usage", ["artifact_id"])
    op.create_index("ix_model_usage_pipeline_pattern", "model_usage", ["pipeline_pattern"])
    op.create_index("ix_model_usage_slot", "model_usage", ["slot"])
    op.create_index(
        "ix_model_usage_analysis",
        "model_usage",
        ["pipeline_pattern", "slot", "artifact_id"],
    )

    op.create_table(
        "lora_series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("opaque_name", sa.String(length=1024), nullable=False),
        sa.Column("display_name", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "correction_state",
            sa.String(length=32),
            server_default="uncorrected",
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opaque_name"),
    )

    op.create_table(
        "lora_series_member",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("model_reference_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=True),
        sa.Column("training_step", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "correction_state",
            sa.String(length=32),
            server_default="uncorrected",
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_artifact.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["model_reference_id"],
            ["model_reference.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["lora_series.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "series_id",
            "model_reference_id",
            name="uq_lora_series_reference",
        ),
    )
    op.create_index("ix_lora_series_member_series_id", "lora_series_member", ["series_id"])
    op.create_index(
        "ix_lora_series_member_model_reference_id",
        "lora_series_member",
        ["model_reference_id"],
    )
    op.create_index(
        "ix_lora_series_member_artifact_id",
        "lora_series_member",
        ["artifact_id"],
    )
    op.create_index(
        "ix_lora_series_step",
        "lora_series_member",
        ["series_id", "training_step"],
    )

    op.create_table(
        "comparison_group",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "comparison_group_member",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["model_artifact.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["comparison_group.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("group_id", "artifact_id"),
    )


def downgrade() -> None:
    op.drop_table("comparison_group_member")
    op.drop_table("comparison_group")
    op.drop_index("ix_lora_series_step", table_name="lora_series_member")
    op.drop_index("ix_lora_series_member_artifact_id", table_name="lora_series_member")
    op.drop_index(
        "ix_lora_series_member_model_reference_id",
        table_name="lora_series_member",
    )
    op.drop_index("ix_lora_series_member_series_id", table_name="lora_series_member")
    op.drop_table("lora_series_member")
    op.drop_table("lora_series")
    op.drop_index("ix_model_usage_analysis", table_name="model_usage")
    op.drop_index("ix_model_usage_slot", table_name="model_usage")
    op.drop_index("ix_model_usage_pipeline_pattern", table_name="model_usage")
    op.drop_index("ix_model_usage_artifact_id", table_name="model_usage")
    op.drop_index("ix_model_usage_model_reference_id", table_name="model_usage")
    op.drop_index("ix_model_usage_observation_id", table_name="model_usage")
    op.drop_index("ix_model_usage_node_id", table_name="model_usage")
    op.drop_index("ix_model_usage_snapshot_id", table_name="model_usage")
    op.drop_table("model_usage")
    op.drop_index("ix_model_reference_resolution", table_name="model_reference")
    op.drop_index("ix_model_reference_resolution_state", table_name="model_reference")
    op.drop_index("ix_model_reference_availability", table_name="model_reference")
    op.drop_index("ix_model_reference_reference_type", table_name="model_reference")
    op.drop_index("ix_model_reference_artifact_id", table_name="model_reference")
    op.drop_table("model_reference")
    op.drop_index("ix_model_artifact_registry_state", table_name="model_artifact")
    op.drop_index("ix_model_artifact_lineage", table_name="model_artifact")
    op.drop_index("ix_model_artifact_architecture_family", table_name="model_artifact")
    op.drop_index("ix_model_artifact_enrichment_state", table_name="model_artifact")
    op.drop_index("ix_model_artifact_availability", table_name="model_artifact")
    op.drop_index("ix_model_artifact_identity_state", table_name="model_artifact")
    op.drop_index("ix_model_artifact_provider_version_id", table_name="model_artifact")
    op.drop_index("ix_model_artifact_provider_model_id", table_name="model_artifact")
    op.drop_index("ix_model_artifact_sha256", table_name="model_artifact")
    op.drop_index("ix_model_artifact_file_name", table_name="model_artifact")
    op.drop_index("ix_model_artifact_artifact_type", table_name="model_artifact")
    op.drop_table("model_artifact")
    op.drop_index("ix_workflow_node_definition_match_state", table_name="workflow_node")
    op.drop_index("ix_workflow_node_node_definition_id", table_name="workflow_node")
    op.drop_constraint(
        "fk_workflow_node_node_definition",
        "workflow_node",
        type_="foreignkey",
    )
    op.drop_column("workflow_node", "definition_confidence")
    op.drop_column("workflow_node", "definition_match_state")
    op.drop_column("workflow_node", "node_definition_id")
    op.drop_index("ix_node_semantic_mapping_state", table_name="node_semantic_mapping")
    op.drop_index(
        "ix_node_semantic_mapping_semantic_type",
        table_name="node_semantic_mapping",
    )
    op.drop_index(
        "ix_node_semantic_mapping_node_definition_id",
        table_name="node_semantic_mapping",
    )
    op.drop_table("node_semantic_mapping")
    op.drop_index("ix_node_definition_review", table_name="node_definition")
    op.drop_index("ix_node_definition_mapping_state", table_name="node_definition")
    op.drop_index("ix_node_definition_is_present", table_name="node_definition")
    op.drop_index("ix_node_definition_schema_fingerprint", table_name="node_definition")
    op.drop_index("ix_node_definition_class_type", table_name="node_definition")
    op.drop_index("ix_node_definition_source_snapshot_id", table_name="node_definition")
    op.drop_table("node_definition")
    op.drop_index("ix_registry_sync_run_node_snapshot_id", table_name="registry_sync_run")
    op.drop_index("ix_registry_sync_run_status", table_name="registry_sync_run")
    op.drop_index("ix_registry_sync_run_registry_kind", table_name="registry_sync_run")
    op.drop_table("registry_sync_run")
    op.drop_index(
        "ix_node_schema_snapshot_object_info_sha256",
        table_name="node_schema_snapshot",
    )
    op.drop_table("node_schema_snapshot")
