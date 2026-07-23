"""Create manual evaluation, organization, and review-session records.

Revision ID: 0005_manual_evaluation
Revises: 0004_node_model_registries
Create Date: 2026-07-24
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_manual_evaluation"
down_revision: str | None = "0004_node_model_registries"
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


def _seed_id(value: str) -> object:
    return uuid5(NAMESPACE_URL, f"comfy-gallery:{value}")


CRITERIA = [
    (
        "core.aesthetic_appeal",
        "core",
        "any",
        "Aesthetic appeal",
        "Judge the overall visual appeal and usefulness of the result.",
        "Unappealing or unusable",
        "Mixed or ordinary appeal",
        "Exceptionally compelling",
    ),
    (
        "core.composition",
        "core",
        "any",
        "Composition",
        "Judge framing, balance, hierarchy, and placement.",
        "Failed or chaotic framing",
        "Readable with noticeable issues",
        "Deliberate and highly effective",
    ),
    (
        "core.prompt_adherence",
        "core",
        "any",
        "Prompt adherence",
        "Judge how well the visible result fulfills the exact prompt.",
        "Misses or contradicts the central request",
        "Captures the main idea but misses important details",
        "Strongly fulfills the explicit intent",
    ),
    (
        "core.logical_plausibility",
        "core",
        "any",
        "Logical plausibility",
        "Judge internal consistency within the intended visual style.",
        "Fundamentally incoherent",
        "Understandable with notable logic problems",
        "Internally consistent within the intended style",
    ),
    (
        "core.technical_execution",
        "core",
        "any",
        "Technical execution",
        "Judge visible control, finish, clarity, and degradation.",
        "Severely degraded",
        "Serviceable with visible quality issues",
        "Highly controlled and well finished",
    ),
    (
        "core.artifact_cleanliness",
        "core",
        "any",
        "Artifact cleanliness",
        "Higher means fewer visible AI-generation defects.",
        "Dominated by generation defects",
        "Some noticeable localized artifacts",
        "No meaningful visible defects",
    ),
    (
        "video.temporal_consistency",
        "video",
        "video",
        "Temporal consistency",
        "Judge stability across frames, including identity and texture drift.",
        "Persistent flicker or identity collapse",
        "Mostly stable with noticeable drift",
        "Consistently stable",
    ),
    (
        "video.motion_quality",
        "video",
        "video",
        "Motion quality",
        "Judge whether the intended motion is natural and controlled.",
        "Broken or unusable motion",
        "Recognizable but stiff or irregular",
        "Smooth, natural, and purposeful",
    ),
    (
        "video.sequence_coherence",
        "video",
        "video",
        "Sequence coherence",
        "Judge whether action and scene progression remain understandable.",
        "Inexplicable progression",
        "Readable action with discontinuities",
        "Logically continuous progression",
    ),
    (
        "character.identity_fidelity",
        "character",
        "any",
        "Identity fidelity",
        "Judge whether the intended character identity is recognizable.",
        "Target identity is unrecognizable",
        "Partial resemblance",
        "Strongly matches defining traits",
    ),
    (
        "character.identity_adaptability",
        "character",
        "any",
        "Identity adaptability",
        "Judge whether requested variation succeeds without losing identity.",
        "Variation destroys identity or is ignored",
        "Partial balance",
        "Requested variation succeeds while identity remains intact",
    ),
]


def upgrade() -> None:
    op.create_table(
        "criterion",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_criterion_stable_key",
        "criterion",
        ["stable_key"],
        unique=True,
    )
    op.create_index("ix_criterion_module", "criterion", ["module"])
    op.create_index("ix_criterion_media_kind", "criterion", ["media_kind"])

    op.create_table(
        "criterion_version",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("criterion_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=256), nullable=False),
        sa.Column("guidance", sa.Text(), nullable=False),
        sa.Column("anchor_0", sa.Text(), nullable=False),
        sa.Column("anchor_5", sa.Text(), nullable=False),
        sa.Column("anchor_10", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["criterion_id"], ["criterion.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("criterion_id", "version", name="uq_criterion_version"),
    )
    op.create_index(
        "ix_criterion_version_criterion_id",
        "criterion_version",
        ["criterion_id"],
    )

    op.create_table(
        "evaluation_template",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stable_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("media_kind", sa.String(length=16), nullable=False),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("locked", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "stable_key",
            "version",
            name="uq_evaluation_template_version",
        ),
    )
    op.create_index(
        "ix_evaluation_template_stable_key",
        "evaluation_template",
        ["stable_key"],
    )
    op.create_index(
        "ix_evaluation_template_media_kind",
        "evaluation_template",
        ["media_kind"],
    )
    op.create_index(
        "ix_evaluation_template_module",
        "evaluation_template",
        ["module"],
    )

    op.create_table(
        "evaluation_template_item",
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_version_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("allow_na", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.ForeignKeyConstraint(
            ["criterion_version_id"],
            ["criterion_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["evaluation_template.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("template_id", "criterion_version_id"),
        sa.UniqueConstraint(
            "template_id",
            "ordinal",
            name="uq_template_item_ordinal",
        ),
    )

    op.create_table(
        "media_collection",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "tag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "saved_filter",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column(
            "expression",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "sort_spec",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "evaluation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "progress_state",
            sa.String(length=32),
            server_default="not_started",
            nullable=False,
        ),
        sa.Column(
            "is_trash",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["reviewer_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["evaluation_template.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "media_id",
            "template_id",
            name="uq_evaluation_media_template",
        ),
    )
    op.create_index("ix_evaluation_media_id", "evaluation", ["media_id"])
    op.create_index("ix_evaluation_template_id", "evaluation", ["template_id"])
    op.create_index("ix_evaluation_reviewer_user_id", "evaluation", ["reviewer_user_id"])
    op.create_index("ix_evaluation_evaluation_kind", "evaluation", ["evaluation_kind"])
    op.create_index("ix_evaluation_progress_state", "evaluation", ["progress_state"])
    op.create_index("ix_evaluation_is_trash", "evaluation", ["is_trash"])
    op.create_index(
        "ix_evaluation_progress",
        "evaluation",
        ["evaluation_kind", "progress_state", "is_trash"],
    )

    op.create_table(
        "evaluation_score",
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_version_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("na_reason", sa.String(length=1024), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "(state = 'scored' AND value >= 0 AND value <= 10) OR (state = 'na' AND value IS NULL)",
            name="ck_evaluation_score_state_value",
        ),
        sa.ForeignKeyConstraint(
            ["criterion_version_id"],
            ["criterion_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluation.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("evaluation_id", "criterion_version_id"),
    )
    op.create_table(
        "score_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("criterion_version_id", sa.Uuid(), nullable=False),
        sa.Column("old_state", sa.String(length=16), nullable=False),
        sa.Column("old_value", sa.Integer(), nullable=True),
        sa.Column("old_na_reason", sa.String(length=1024), nullable=True),
        sa.Column("new_state", sa.String(length=16), nullable=False),
        sa.Column("new_value", sa.Integer(), nullable=True),
        sa.Column("new_na_reason", sa.String(length=1024), nullable=True),
        sa.Column("evaluation_version", sa.Integer(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["criterion_version_id"],
            ["criterion_version.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluation.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_score_revision_evaluation_id", "score_revision", ["evaluation_id"])
    op.create_index(
        "ix_score_revision_criterion_version_id",
        "score_revision",
        ["criterion_version_id"],
    )
    op.create_table(
        "evaluation_disposition_revision",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evaluation_id", sa.Uuid(), nullable=False),
        sa.Column("old_is_trash", sa.Boolean(), nullable=False),
        sa.Column("new_is_trash", sa.Boolean(), nullable=False),
        sa.Column("evaluation_version", sa.Integer(), nullable=False),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["app_user.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["evaluation.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_evaluation_disposition_revision_evaluation_id",
        "evaluation_disposition_revision",
        ["evaluation_id"],
    )

    op.create_table(
        "collection_item",
        sa.Column("collection_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["collection_id"],
            ["media_collection.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "media_id"),
    )
    op.create_table(
        "media_tag",
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tag_id"], ["tag.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("media_id", "tag_id"),
    )

    op.create_table(
        "review_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "scope_snapshot",
            _jsonb(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("ordering_mode", sa.String(length=32), nullable=False),
        sa.Column("random_seed", sa.BigInteger(), nullable=True),
        sa.Column(
            "optional_modules",
            _jsonb(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("current_cursor", sa.Integer(), server_default="0", nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "last_opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["app_user.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_session_status", "review_session", ["status"])
    op.create_index(
        "ix_review_session_created_by_user_id",
        "review_session",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_review_session_resume",
        "review_session",
        ["status", "last_opened_at"],
    )
    op.create_table(
        "review_session_item",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["media_id"], ["media.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["review_session.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "media_id",
            name="uq_review_session_item_media",
        ),
        sa.UniqueConstraint(
            "session_id",
            "ordinal",
            name="uq_review_session_item_ordinal",
        ),
    )
    op.create_index(
        "ix_review_session_item_session_id",
        "review_session_item",
        ["session_id"],
    )
    op.create_index(
        "ix_review_session_item_media_id",
        "review_session_item",
        ["media_id"],
    )

    _seed_catalog()


def _seed_catalog() -> None:
    criterion_table = sa.table(
        "criterion",
        sa.column("id", sa.Uuid()),
        sa.column("stable_key", sa.String()),
        sa.column("module", sa.String()),
        sa.column("media_kind", sa.String()),
        sa.column("active", sa.Boolean()),
    )
    criterion_version_table = sa.table(
        "criterion_version",
        sa.column("id", sa.Uuid()),
        sa.column("criterion_id", sa.Uuid()),
        sa.column("version", sa.Integer()),
        sa.column("label", sa.String()),
        sa.column("guidance", sa.Text()),
        sa.column("anchor_0", sa.Text()),
        sa.column("anchor_5", sa.Text()),
        sa.column("anchor_10", sa.Text()),
    )
    template_table = sa.table(
        "evaluation_template",
        sa.column("id", sa.Uuid()),
        sa.column("stable_key", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("media_kind", sa.String()),
        sa.column("module", sa.String()),
        sa.column("locked", sa.Boolean()),
    )
    template_item_table = sa.table(
        "evaluation_template_item",
        sa.column("template_id", sa.Uuid()),
        sa.column("criterion_version_id", sa.Uuid()),
        sa.column("ordinal", sa.Integer()),
        sa.column("required", sa.Boolean()),
        sa.column("allow_na", sa.Boolean()),
    )
    op.bulk_insert(
        criterion_table,
        [
            {
                "id": _seed_id(f"criterion:{row[0]}"),
                "stable_key": row[0],
                "module": row[1],
                "media_kind": row[2],
                "active": True,
            }
            for row in CRITERIA
        ],
    )
    op.bulk_insert(
        criterion_version_table,
        [
            {
                "id": _seed_id(f"criterion-version:{row[0]}:1"),
                "criterion_id": _seed_id(f"criterion:{row[0]}"),
                "version": 1,
                "label": row[3],
                "guidance": row[4],
                "anchor_0": row[5],
                "anchor_5": row[6],
                "anchor_10": row[7],
            }
            for row in CRITERIA
        ],
    )
    templates = [
        ("image.core", "Image core V1", "image", "core"),
        ("video.core", "Video core V1", "video", "core"),
        ("image.character", "Image character V1", "image", "character"),
        ("video.character", "Video character V1", "video", "character"),
    ]
    op.bulk_insert(
        template_table,
        [
            {
                "id": _seed_id(f"template:{row[0]}:1"),
                "stable_key": row[0],
                "version": 1,
                "name": row[1],
                "media_kind": row[2],
                "module": row[3],
                "locked": True,
            }
            for row in templates
        ],
    )
    by_module = {
        "image.core": [row[0] for row in CRITERIA if row[1] == "core"],
        "video.core": [row[0] for row in CRITERIA if row[1] in {"core", "video"}],
        "image.character": [row[0] for row in CRITERIA if row[1] == "character"],
        "video.character": [row[0] for row in CRITERIA if row[1] == "character"],
    }
    op.bulk_insert(
        template_item_table,
        [
            {
                "template_id": _seed_id(f"template:{template_key}:1"),
                "criterion_version_id": _seed_id(f"criterion-version:{criterion_key}:1"),
                "ordinal": ordinal,
                "required": True,
                "allow_na": True,
            }
            for template_key, criterion_keys in by_module.items()
            for ordinal, criterion_key in enumerate(criterion_keys)
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_review_session_item_media_id", table_name="review_session_item")
    op.drop_index("ix_review_session_item_session_id", table_name="review_session_item")
    op.drop_table("review_session_item")
    op.drop_index("ix_review_session_resume", table_name="review_session")
    op.drop_index("ix_review_session_created_by_user_id", table_name="review_session")
    op.drop_index("ix_review_session_status", table_name="review_session")
    op.drop_table("review_session")
    op.drop_table("media_tag")
    op.drop_table("collection_item")
    op.drop_index(
        "ix_evaluation_disposition_revision_evaluation_id",
        table_name="evaluation_disposition_revision",
    )
    op.drop_table("evaluation_disposition_revision")
    op.drop_index("ix_score_revision_criterion_version_id", table_name="score_revision")
    op.drop_index("ix_score_revision_evaluation_id", table_name="score_revision")
    op.drop_table("score_revision")
    op.drop_table("evaluation_score")
    op.drop_index("ix_evaluation_progress", table_name="evaluation")
    op.drop_index("ix_evaluation_is_trash", table_name="evaluation")
    op.drop_index("ix_evaluation_progress_state", table_name="evaluation")
    op.drop_index("ix_evaluation_evaluation_kind", table_name="evaluation")
    op.drop_index("ix_evaluation_reviewer_user_id", table_name="evaluation")
    op.drop_index("ix_evaluation_template_id", table_name="evaluation")
    op.drop_index("ix_evaluation_media_id", table_name="evaluation")
    op.drop_table("evaluation")
    op.drop_table("saved_filter")
    op.drop_table("tag")
    op.drop_table("media_collection")
    op.drop_table("evaluation_template_item")
    op.drop_index("ix_evaluation_template_module", table_name="evaluation_template")
    op.drop_index("ix_evaluation_template_media_kind", table_name="evaluation_template")
    op.drop_index("ix_evaluation_template_stable_key", table_name="evaluation_template")
    op.drop_table("evaluation_template")
    op.drop_index("ix_criterion_version_criterion_id", table_name="criterion_version")
    op.drop_table("criterion_version")
    op.drop_index("ix_criterion_media_kind", table_name="criterion")
    op.drop_index("ix_criterion_module", table_name="criterion")
    op.drop_index("ix_criterion_stable_key", table_name="criterion")
    op.drop_table("criterion")
