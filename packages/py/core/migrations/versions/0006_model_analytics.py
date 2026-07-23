"""Create immutable model-focused analytics records.

Revision ID: 0006_model_analytics
Revises: 0005_manual_evaluation
Create Date: 2026-07-24
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_model_analytics"
down_revision: str | None = "0005_manual_evaluation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _jsonb() -> postgresql.JSONB:
    return postgresql.JSONB(astext_type=sa.Text())


def _equal_profile_id() -> object:
    return uuid5(NAMESPACE_URL, "comfy-gallery:weighting-profile:equal:v1")


def upgrade() -> None:
    op.create_table(
        "weighting_profile",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("weights", _jsonb(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column(
            "default_weight",
            sa.Float(),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.Uuid()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stable_key",
            "version",
            name="uq_weighting_profile_version",
        ),
    )
    op.create_index(
        "ix_weighting_profile_stable_key",
        "weighting_profile",
        ["stable_key"],
    )
    op.create_index(
        "ix_weighting_profile_created_by_user_id",
        "weighting_profile",
        ["created_by_user_id"],
    )

    op.create_table(
        "analysis_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "filter_spec",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "report_spec",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("weighting_profile_id", sa.Uuid(), nullable=False),
        sa.Column("calculation_version", sa.String(length=64), nullable=False),
        sa.Column("parent_run_id", sa.Uuid()),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("media_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "excluded_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("group_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "effective_criteria",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "warnings",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "context",
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
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["weighting_profile_id"],
            ["weighting_profile.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_run_id"],
            ["analysis_run.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_run_report_type", "analysis_run", ["report_type"])
    op.create_index("ix_analysis_run_status", "analysis_run", ["status"])
    op.create_index(
        "ix_analysis_run_weighting_profile_id",
        "analysis_run",
        ["weighting_profile_id"],
    )
    op.create_index("ix_analysis_run_parent_run_id", "analysis_run", ["parent_run_id"])
    op.create_index(
        "ix_analysis_run_created_by_user_id",
        "analysis_run",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_analysis_run_created",
        "analysis_run",
        ["created_by_user_id", "created_at"],
    )

    op.create_table(
        "analysis_member",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid()),
        sa.Column("template_id", sa.Uuid()),
        sa.Column("evaluation_version", sa.Integer()),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("exclusion_reason", sa.String(length=64)),
        sa.Column(
            "group_keys",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "model_context",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("composite_score", sa.Float()),
        sa.Column(
            "included_criterion_keys",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_run.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluation.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["evaluation_template.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "media_id", name="uq_analysis_member_media"),
    )
    op.create_index("ix_analysis_member_run_id", "analysis_member", ["run_id"])
    op.create_index("ix_analysis_member_media_id", "analysis_member", ["media_id"])
    op.create_index(
        "ix_analysis_member_evaluation_id",
        "analysis_member",
        ["evaluation_id"],
    )
    op.create_index("ix_analysis_member_template_id", "analysis_member", ["template_id"])
    op.create_index("ix_analysis_member_included", "analysis_member", ["included"])
    op.create_index(
        "ix_analysis_member_exclusion_reason",
        "analysis_member",
        ["exclusion_reason"],
    )
    op.create_index(
        "ix_analysis_member_inclusion",
        "analysis_member",
        ["run_id", "included", "exclusion_reason"],
    )

    op.create_table(
        "analysis_score_snapshot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_version_id", sa.Uuid(), nullable=False),
        sa.Column("score_revision_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_key", sa.String(length=128), nullable=False),
        sa.Column("criterion_label", sa.String(length=256), nullable=False),
        sa.Column("score_state", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Integer()),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["analysis_member.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["criterion_version_id"],
            ["criterion_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["score_revision_id"],
            ["score_revision.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id",
            "criterion_version_id",
            name="uq_analysis_score_criterion",
        ),
    )
    op.create_index(
        "ix_analysis_score_snapshot_member_id",
        "analysis_score_snapshot",
        ["member_id"],
    )
    op.create_index(
        "ix_analysis_score_snapshot_criterion_version_id",
        "analysis_score_snapshot",
        ["criterion_version_id"],
    )
    op.create_index(
        "ix_analysis_score_snapshot_score_revision_id",
        "analysis_score_snapshot",
        ["score_revision_id"],
    )
    op.create_index(
        "ix_analysis_score_snapshot_criterion_key",
        "analysis_score_snapshot",
        ["criterion_key"],
    )

    op.create_table(
        "analysis_result",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("group_hash", sa.String(length=64), nullable=False),
        sa.Column("group_key", sa.Text(), nullable=False),
        sa.Column("group_label", sa.Text(), nullable=False),
        sa.Column(
            "dimensions",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("criterion_key", sa.String(length=128), nullable=False),
        sa.Column("criterion_label", sa.String(length=256), nullable=False),
        sa.Column("eligible_count", sa.Integer(), nullable=False),
        sa.Column("scored_count", sa.Integer(), nullable=False),
        sa.Column("na_count", sa.Integer(), nullable=False),
        sa.Column("not_collected_count", sa.Integer(), nullable=False),
        sa.Column("trash_count", sa.Integer(), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("mean", sa.Float()),
        sa.Column("median", sa.Float()),
        sa.Column("minimum", sa.Float()),
        sa.Column("maximum", sa.Float()),
        sa.Column("q1", sa.Float()),
        sa.Column("q3", sa.Float()),
        sa.Column("ci_low", sa.Float()),
        sa.Column("ci_high", sa.Float()),
        sa.Column("reference_group_key", sa.Text()),
        sa.Column("difference_from_reference", sa.Float()),
        sa.Column("effect_size", sa.Float()),
        sa.Column("evidence_strength", sa.String(length=32), nullable=False),
        sa.Column(
            "histogram",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "context",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id",
            "group_hash",
            "criterion_key",
            name="uq_analysis_result_group_criterion",
        ),
    )
    op.create_index("ix_analysis_result_run_id", "analysis_result", ["run_id"])
    op.create_index(
        "ix_analysis_result_report",
        "analysis_result",
        ["run_id", "criterion_key", "mean"],
    )

    profile_table = sa.table(
        "weighting_profile",
        sa.column("id", sa.Uuid()),
        sa.column("stable_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("weights", _jsonb()),
        sa.column("default_weight", sa.Float()),
        sa.column("is_builtin", sa.Boolean()),
    )
    op.bulk_insert(
        profile_table,
        [
            {
                "id": _equal_profile_id(),
                "stable_key": "equal",
                "version": 1,
                "name": "Equal weight",
                "description": "Every collected criterion contributes equally.",
                "weights": {},
                "default_weight": 1.0,
                "is_builtin": True,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("analysis_result")
    op.drop_table("analysis_score_snapshot")
    op.drop_table("analysis_member")
    op.drop_table("analysis_run")
    op.drop_table("weighting_profile")
