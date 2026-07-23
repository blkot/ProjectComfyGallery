from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from comfy_gallery_core.db.base import Base, TimestampMixin

json_type = JSON().with_variant(JSONB(), "postgresql")


class User(TimestampMixin, Base):
    __tablename__ = "app_user"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    sessions: Mapped[list[WebSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_tokens: Mapped[list[ApiToken]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    evaluations: Mapped[list[Evaluation]] = relationship(back_populates="reviewer")
    review_sessions: Mapped[list[ReviewSession]] = relationship(back_populates="created_by")
    weighting_profiles: Mapped[list[WeightingProfile]] = relationship(back_populates="created_by")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="created_by")
    export_runs: Mapped[list[ExportRun]] = relationship(back_populates="created_by")


class WebSession(Base):
    __tablename__ = "web_session"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class ApiToken(Base):
    __tablename__ = "api_token"
    __table_args__ = (Index("ix_api_token_user_active", "user_id", "revoked_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="api_tokens")


class Media(TimestampMixin, Base):
    __tablename__ = "media"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="processing",
        server_default="processing",
        index=True,
    )
    detected_format: Mapped[str | None] = mapped_column(String(32))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    frame_rate: Mapped[float | None] = mapped_column(Float)
    container: Mapped[str | None] = mapped_column(String(64))
    video_codec: Mapped[str | None] = mapped_column(String(64))
    audio_codec: Mapped[str | None] = mapped_column(String(64))
    probe_data: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    warning_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(Text)

    asset: Mapped[MediaAsset] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
        uselist=False,
    )
    derivatives: Mapped[list[Derivative]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    source_occurrences: Mapped[list[SourceOccurrence]] = relationship(back_populates="media")
    upload_items: Mapped[list[UploadItem]] = relationship(back_populates="media")
    workflow_snapshot: Mapped[WorkflowSnapshot | None] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
        uselist=False,
    )
    evaluations: Mapped[list[Evaluation]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    collection_memberships: Mapped[list[CollectionItem]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    tag_memberships: Mapped[list[MediaTag]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    review_memberships: Mapped[list[ReviewSessionItem]] = relationship(
        back_populates="media",
        cascade="all, delete-orphan",
    )
    analysis_memberships: Mapped[list[AnalysisMember]] = relationship(back_populates="media")


class MediaAsset(Base):
    __tablename__ = "media_asset"

    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_extension: Mapped[str | None] = mapped_column(String(32))
    managed_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    media: Mapped[Media] = relationship(back_populates="asset")


class Derivative(Base):
    __tablename__ = "derivative"
    __table_args__ = (
        UniqueConstraint(
            "media_id",
            "kind",
            "recipe_version",
            name="uq_derivative_media_kind_recipe",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    recipe_version: Mapped[str] = mapped_column(String(32), nullable=False)
    managed_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    container: Mapped[str | None] = mapped_column(String(64))
    codec: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    media: Mapped[Media] = relationship(back_populates="derivatives")


class SourceRoot(TimestampMixin, Base):
    __tablename__ = "source_root"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scans: Mapped[list[ScanBatch]] = relationship(back_populates="source_root")
    occurrences: Mapped[list[SourceOccurrence]] = relationship(back_populates="source_root")


class ScanBatch(Base):
    __tablename__ = "scan_batch"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    source_root_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_root.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    discovered_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    imported_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    missing_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)

    source_root: Mapped[SourceRoot] = relationship(back_populates="scans")


class SourceOccurrence(TimestampMixin, Base):
    __tablename__ = "source_occurrence"
    __table_args__ = (
        Index(
            "ix_source_occurrence_current_path",
            "source_root_id",
            "relative_path",
            "superseded_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    source_root_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_root.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )
    relative_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mtime_ns: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="present",
        server_default="present",
        index=True,
    )
    first_seen_scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("scan_batch.id", ondelete="RESTRICT"),
        nullable=False,
    )
    last_seen_scan_id: Mapped[UUID] = mapped_column(
        ForeignKey("scan_batch.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)

    source_root: Mapped[SourceRoot] = relationship(back_populates="occurrences")
    media: Mapped[Media | None] = relationship(back_populates="source_occurrences")


class UploadBatch(Base):
    __tablename__ = "upload_batch"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="receiving",
        server_default="receiving",
        index=True,
    )
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    queued_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list[UploadItem]] = relationship(
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class UploadItem(Base):
    __tablename__ = "upload_item"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("upload_batch.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media.id", ondelete="SET NULL"),
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    staging_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    byte_size: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="receiving",
        server_default="receiving",
        index=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[UploadBatch] = relationship(back_populates="items")
    media: Mapped[Media | None] = relationship(back_populates="upload_items")


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (Index("ix_job_resource", "resource_type", "resource_id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    queue: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64))
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    progress_current: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    progress_total: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cancel_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stage_attempts: Mapped[list[JobStageAttempt]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class JobStageAttempt(Base):
    __tablename__ = "job_stage_attempt"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "stage",
            "job_attempt",
            name="uq_job_stage_attempt",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("job.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    job_attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    job: Mapped[Job] = relationship(back_populates="stage_attempts")


class ExportRun(Base):
    __tablename__ = "export_run"
    __table_args__ = (Index("ix_export_run_created", "created_by_user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    export_schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1",
        server_default="1",
    )
    requested_options: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    artifact_path: Mapped[str | None] = mapped_column(String(1024), unique=True)
    sha256: Mapped[str | None] = mapped_column(String(64))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    table_counts: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_by: Mapped[User] = relationship(back_populates="export_runs")


class WorkflowSnapshot(Base):
    __tablename__ = "workflow_snapshot"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    reader_name: Mapped[str] = mapped_column(String(80), nullable=False)
    reader_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_carrier: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_metadata: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    raw_api_prompt_text: Mapped[str | None] = mapped_column(Text)
    raw_visual_workflow_text: Mapped[str | None] = mapped_column(Text)
    api_prompt: Mapped[dict[str, object] | None] = mapped_column(json_type)
    visual_workflow: Mapped[dict[str, object] | None] = mapped_column(json_type)
    api_prompt_status: Mapped[str] = mapped_column(String(32), nullable=False)
    visual_workflow_status: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    issue_details: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    graph_version: Mapped[str | None] = mapped_column(String(32))
    api_node_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    visual_node_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    edge_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    media: Mapped[Media] = relationship(back_populates="workflow_snapshot")
    nodes: Mapped[list[WorkflowNode]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list[WorkflowEdge]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )
    extraction_runs: Mapped[list[ExtractionRun]] = relationship(
        back_populates="snapshot",
        cascade="all, delete-orphan",
    )


class WorkflowNode(Base):
    __tablename__ = "workflow_node"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "representation",
            "original_node_id",
            name="uq_workflow_node_identity",
        ),
        Index("ix_workflow_node_class_type", "class_type"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_definition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("node_definition.id", ondelete="SET NULL"),
        index=True,
    )
    definition_match_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unresolved",
        server_default="unresolved",
        index=True,
    )
    definition_confidence: Mapped[float | None] = mapped_column(Float)
    representation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    original_node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    class_type: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str | None] = mapped_column(String(1024))
    module_hint: Mapped[str | None] = mapped_column(String(512))
    mode: Mapped[int | None] = mapped_column(Integer)
    raw_properties: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    raw_widgets: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    raw_inputs: Mapped[dict[str, object] | list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    snapshot: Mapped[WorkflowSnapshot] = relationship(back_populates="nodes")
    values: Mapped[list[WorkflowValue]] = relationship(
        back_populates="node",
        cascade="all, delete-orphan",
    )
    observations: Mapped[list[SemanticObservation]] = relationship(back_populates="node")
    node_definition: Mapped[NodeDefinition | None] = relationship(back_populates="workflow_nodes")


class WorkflowEdge(Base):
    __tablename__ = "workflow_edge"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "representation",
            "ordinal",
            name="uq_workflow_edge_ordinal",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    representation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    original_link_id: Mapped[str | None] = mapped_column(String(128))
    source_node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_output_index: Mapped[int | None] = mapped_column(Integer)
    destination_node_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_input_index: Mapped[int | None] = mapped_column(Integer)
    destination_input_name: Mapped[str | None] = mapped_column(String(512))
    declared_type: Mapped[str | None] = mapped_column(String(256))
    raw_link: Mapped[list[object] | dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
    )

    snapshot: Mapped[WorkflowSnapshot] = relationship(back_populates="edges")


class WorkflowValue(Base):
    __tablename__ = "workflow_value"
    __table_args__ = (
        UniqueConstraint(
            "node_id",
            "locator",
            name="uq_workflow_value_locator",
        ),
        Index("ix_workflow_value_input_name", "input_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    node_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_node.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locator: Mapped[str] = mapped_column(String(512), nullable=False)
    input_name: Mapped[str | None] = mapped_column(String(512))
    input_index: Mapped[int | None] = mapped_column(Integer)
    value_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    raw_value: Mapped[object] = mapped_column(json_type, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)

    node: Mapped[WorkflowNode] = relationship(back_populates="values")


class ExtractionRun(Base):
    __tablename__ = "extraction_run"
    __table_args__ = (Index("ix_extraction_run_snapshot_current", "snapshot_id", "is_current"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extractor_name: Mapped[str] = mapped_column(String(80), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(32), nullable=False)
    graph_version: Mapped[str] = mapped_column(String(32), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    observation_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    error_details: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    snapshot: Mapped[WorkflowSnapshot] = relationship(back_populates="extraction_runs")
    observations: Mapped[list[SemanticObservation]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class SemanticObservation(Base):
    __tablename__ = "semantic_observation"
    __table_args__ = (Index("ix_semantic_observation_type_role", "observation_type", "role"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("extraction_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_node.id", ondelete="SET NULL"),
        index=True,
    )
    observation_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(128))
    value: Mapped[object] = mapped_column(json_type, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    correction_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uncorrected",
        server_default="uncorrected",
    )
    evidence: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    run: Mapped[ExtractionRun] = relationship(back_populates="observations")
    node: Mapped[WorkflowNode | None] = relationship(back_populates="observations")


class RegistrySyncRun(Base):
    __tablename__ = "registry_sync_run"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    registry_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    requested_options: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    current_stage: Mapped[str | None] = mapped_column(String(80))
    stage_status: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    counts: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    source_versions: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    node_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("node_schema_snapshot.id", ondelete="SET NULL"),
        index=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    node_snapshot: Mapped[NodeSchemaSnapshot | None] = relationship(back_populates="sync_runs")


class NodeSchemaSnapshot(Base):
    __tablename__ = "node_schema_snapshot"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    comfyui_version: Mapped[str | None] = mapped_column(String(128))
    object_info_sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    raw_object_info: Mapped[dict[str, object]] = mapped_column(json_type, nullable=False)
    definition_count: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    sync_runs: Mapped[list[RegistrySyncRun]] = relationship(back_populates="node_snapshot")
    definitions: Mapped[list[NodeDefinition]] = relationship(back_populates="source_snapshot")


class NodeDefinition(TimestampMixin, Base):
    __tablename__ = "node_definition"
    __table_args__ = (
        UniqueConstraint(
            "class_type",
            "python_module",
            "schema_fingerprint",
            name="uq_node_definition_variant",
        ),
        Index("ix_node_definition_review", "mapping_state", "is_present"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    source_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("node_schema_snapshot.id", ondelete="SET NULL"),
        index=True,
    )
    class_type: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    python_module: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
        server_default="",
    )
    schema_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(1024))
    category: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    output_schema: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    raw_definition: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    is_present: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    mapping_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
        index=True,
    )
    workflow_occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    source_snapshot: Mapped[NodeSchemaSnapshot | None] = relationship(back_populates="definitions")
    mappings: Mapped[list[NodeSemanticMapping]] = relationship(
        back_populates="node_definition",
        cascade="all, delete-orphan",
    )
    workflow_nodes: Mapped[list[WorkflowNode]] = relationship(back_populates="node_definition")


class NodeSemanticMapping(TimestampMixin, Base):
    __tablename__ = "node_semantic_mapping"
    __table_args__ = (
        UniqueConstraint(
            "node_definition_id",
            "locator",
            name="uq_node_semantic_mapping_locator",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    node_definition_id: Mapped[UUID] = mapped_column(
        ForeignKey("node_definition.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    locator: Mapped[str] = mapped_column(String(512), nullable=False)
    input_name: Mapped[str | None] = mapped_column(String(512))
    input_index: Mapped[int | None] = mapped_column(Integer)
    semantic_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    correction_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uncorrected",
        server_default="uncorrected",
    )
    evidence: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    node_definition: Mapped[NodeDefinition] = relationship(back_populates="mappings")


class ModelArtifact(TimestampMixin, Base):
    __tablename__ = "model_artifact"
    __table_args__ = (
        UniqueConstraint("sha256", name="uq_model_artifact_sha256"),
        Index("ix_model_artifact_registry_state", "artifact_type", "availability"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_name: Mapped[str | None] = mapped_column(String(1024), index=True)
    file_path: Mapped[str | None] = mapped_column(String(2048))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="local",
        server_default="local",
    )
    provider_model_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_version_id: Mapped[str | None] = mapped_column(String(128), index=True)
    provider_url: Mapped[str | None] = mapped_column(Text)
    identity_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    enrichment_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    architecture_family: Mapped[str | None] = mapped_column(String(256), index=True)
    lineage: Mapped[str | None] = mapped_column(String(256), index=True)
    variant: Mapped[str | None] = mapped_column(String(256))
    precision: Mapped[str | None] = mapped_column(String(64))
    quantization: Mapped[str | None] = mapped_column(String(64))
    raw_inventory: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    raw_provider_metadata: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    manual_overrides: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    references: Mapped[list[ModelReference]] = relationship(back_populates="artifact")
    usages: Mapped[list[ModelUsage]] = relationship(back_populates="artifact")
    comparison_memberships: Mapped[list[ComparisonGroupMember]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class ModelReference(TimestampMixin, Base):
    __tablename__ = "model_reference"
    __table_args__ = (
        UniqueConstraint(
            "reference_type",
            "normalized_value",
            name="uq_model_reference_value",
        ),
        Index("ix_model_reference_resolution", "resolution_state", "availability"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_artifact.id", ondelete="SET NULL"),
        index=True,
    )
    reference_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    resolution_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    match_method: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float | None] = mapped_column(Float)
    occurrence_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    candidate_artifact_ids: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    manual_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    artifact: Mapped[ModelArtifact | None] = relationship(back_populates="references")
    usages: Mapped[list[ModelUsage]] = relationship(
        back_populates="model_reference",
        cascade="all, delete-orphan",
    )
    series_memberships: Mapped[list[LoraSeriesMember]] = relationship(
        back_populates="model_reference",
        cascade="all, delete-orphan",
    )


class ModelUsage(TimestampMixin, Base):
    __tablename__ = "model_usage"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id",
            "node_id",
            "model_reference_id",
            "observation_type",
            name="uq_model_usage_occurrence",
        ),
        Index("ix_model_usage_analysis", "pipeline_pattern", "slot", "artifact_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflow_snapshot.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_node.id", ondelete="SET NULL"),
        index=True,
    )
    observation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("semantic_observation.id", ondelete="SET NULL"),
        index=True,
    )
    model_reference_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_reference.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_artifact.id", ondelete="SET NULL"),
        index=True,
    )
    observation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    pipeline_pattern: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    slot: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    usage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    correction_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uncorrected",
        server_default="uncorrected",
    )
    evidence: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    artifact: Mapped[ModelArtifact | None] = relationship(back_populates="usages")
    model_reference: Mapped[ModelReference] = relationship(back_populates="usages")


class LoraSeries(TimestampMixin, Base):
    __tablename__ = "lora_series"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    opaque_name: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    correction_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uncorrected",
        server_default="uncorrected",
    )

    members: Mapped[list[LoraSeriesMember]] = relationship(
        back_populates="series",
        cascade="all, delete-orphan",
    )


class LoraSeriesMember(TimestampMixin, Base):
    __tablename__ = "lora_series_member"
    __table_args__ = (
        UniqueConstraint(
            "series_id",
            "model_reference_id",
            name="uq_lora_series_reference",
        ),
        Index("ix_lora_series_step", "series_id", "training_step"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    series_id: Mapped[UUID] = mapped_column(
        ForeignKey("lora_series.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_reference_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_reference.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_artifact.id", ondelete="SET NULL"),
        index=True,
    )
    training_step: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    correction_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="uncorrected",
        server_default="uncorrected",
    )

    series: Mapped[LoraSeries] = relationship(back_populates="members")
    model_reference: Mapped[ModelReference] = relationship(back_populates="series_memberships")


class ComparisonGroup(TimestampMixin, Base):
    __tablename__ = "comparison_group"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    members: Mapped[list[ComparisonGroupMember]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class ComparisonGroupMember(Base):
    __tablename__ = "comparison_group_member"

    group_id: Mapped[UUID] = mapped_column(
        ForeignKey("comparison_group.id", ondelete="CASCADE"),
        primary_key=True,
    )
    artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("model_artifact.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    group: Mapped[ComparisonGroup] = relationship(back_populates="members")
    artifact: Mapped[ModelArtifact] = relationship(back_populates="comparison_memberships")


class Criterion(TimestampMixin, Base):
    __tablename__ = "criterion"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    stable_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    versions: Mapped[list[CriterionVersion]] = relationship(
        back_populates="criterion",
        cascade="all, delete-orphan",
    )


class CriterionVersion(TimestampMixin, Base):
    __tablename__ = "criterion_version"
    __table_args__ = (UniqueConstraint("criterion_id", "version", name="uq_criterion_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    criterion_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(256), nullable=False)
    guidance: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_0: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_5: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_10: Mapped[str] = mapped_column(Text, nullable=False)

    criterion: Mapped[Criterion] = relationship(back_populates="versions")
    template_memberships: Mapped[list[EvaluationTemplateItem]] = relationship(
        back_populates="criterion_version"
    )


class EvaluationTemplate(TimestampMixin, Base):
    __tablename__ = "evaluation_template"
    __table_args__ = (
        UniqueConstraint("stable_key", "version", name="uq_evaluation_template_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    stable_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    media_kind: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    items: Mapped[list[EvaluationTemplateItem]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="EvaluationTemplateItem.ordinal",
    )
    evaluations: Mapped[list[Evaluation]] = relationship(back_populates="template")


class EvaluationTemplateItem(Base):
    __tablename__ = "evaluation_template_item"
    __table_args__ = (UniqueConstraint("template_id", "ordinal", name="uq_template_item_ordinal"),)

    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_template.id", ondelete="CASCADE"),
        primary_key=True,
    )
    criterion_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    allow_na: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    template: Mapped[EvaluationTemplate] = relationship(back_populates="items")
    criterion_version: Mapped[CriterionVersion] = relationship(
        back_populates="template_memberships"
    )


class Evaluation(TimestampMixin, Base):
    __tablename__ = "evaluation"
    __table_args__ = (
        UniqueConstraint("media_id", "template_id", name="uq_evaluation_media_template"),
        Index("ix_evaluation_progress", "evaluation_kind", "progress_state", "is_trash"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation_template.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evaluation_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    progress_state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_started",
        server_default="not_started",
        index=True,
    )
    is_trash: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        index=True,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    media: Mapped[Media] = relationship(back_populates="evaluations")
    template: Mapped[EvaluationTemplate] = relationship(back_populates="evaluations")
    reviewer: Mapped[User] = relationship(back_populates="evaluations")
    scores: Mapped[list[EvaluationScore]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )
    score_revisions: Mapped[list[ScoreRevision]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )
    disposition_revisions: Mapped[list[EvaluationDispositionRevision]] = relationship(
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )
    analysis_memberships: Mapped[list[AnalysisMember]] = relationship(back_populates="evaluation")


class EvaluationScore(TimestampMixin, Base):
    __tablename__ = "evaluation_score"
    __table_args__ = (
        CheckConstraint(
            "(state = 'scored' AND value >= 0 AND value <= 10) OR (state = 'na' AND value IS NULL)",
            name="ck_evaluation_score_state_value",
        ),
    )

    evaluation_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.id", ondelete="CASCADE"),
        primary_key=True,
    )
    criterion_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion_version.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int | None] = mapped_column(Integer)
    na_reason: Mapped[str | None] = mapped_column(String(1024))
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )

    evaluation: Mapped[Evaluation] = relationship(back_populates="scores")
    criterion_version: Mapped[CriterionVersion] = relationship()


class ScoreRevision(Base):
    __tablename__ = "score_revision"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    evaluation_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion_version.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    old_state: Mapped[str] = mapped_column(String(16), nullable=False)
    old_value: Mapped[int | None] = mapped_column(Integer)
    old_na_reason: Mapped[str | None] = mapped_column(String(1024))
    new_state: Mapped[str] = mapped_column(String(16), nullable=False)
    new_value: Mapped[int | None] = mapped_column(Integer)
    new_na_reason: Mapped[str | None] = mapped_column(String(1024))
    evaluation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    evaluation: Mapped[Evaluation] = relationship(back_populates="score_revisions")
    criterion_version: Mapped[CriterionVersion] = relationship()


class EvaluationDispositionRevision(Base):
    __tablename__ = "evaluation_disposition_revision"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    evaluation_id: Mapped[UUID] = mapped_column(
        ForeignKey("evaluation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_is_trash: Mapped[bool] = mapped_column(Boolean, nullable=False)
    new_is_trash: Mapped[bool] = mapped_column(Boolean, nullable=False)
    evaluation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    evaluation: Mapped[Evaluation] = relationship(back_populates="disposition_revisions")


class MediaCollection(TimestampMixin, Base):
    __tablename__ = "media_collection"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )

    items: Mapped[list[CollectionItem]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
    )


class CollectionItem(Base):
    __tablename__ = "collection_item"

    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_collection.id", ondelete="CASCADE"),
        primary_key=True,
    )
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    collection: Mapped[MediaCollection] = relationship(back_populates="items")
    media: Mapped[Media] = relationship(back_populates="collection_memberships")


class Tag(TimestampMixin, Base):
    __tablename__ = "tag"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    color: Mapped[str | None] = mapped_column(String(32))
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )

    media_memberships: Mapped[list[MediaTag]] = relationship(
        back_populates="tag",
        cascade="all, delete-orphan",
    )


class MediaTag(Base):
    __tablename__ = "media_tag"

    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        ForeignKey("tag.id", ondelete="CASCADE"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    media: Mapped[Media] = relationship(back_populates="tag_memberships")
    tag: Mapped[Tag] = relationship(back_populates="media_memberships")


class SavedFilter(TimestampMixin, Base):
    __tablename__ = "saved_filter"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    expression: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    sort_spec: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
    )


class ReviewSession(TimestampMixin, Base):
    __tablename__ = "review_session"
    __table_args__ = (Index("ix_review_session_resume", "status", "last_opened_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    name: Mapped[str | None] = mapped_column(String(256))
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_snapshot: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    ordering_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    random_seed: Mapped[int | None] = mapped_column(BigInteger)
    optional_modules: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    current_cursor: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    last_opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_by: Mapped[User] = relationship(back_populates="review_sessions")
    items: Mapped[list[ReviewSessionItem]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReviewSessionItem.ordinal",
    )


class ReviewSessionItem(Base):
    __tablename__ = "review_session_item"
    __table_args__ = (
        UniqueConstraint("session_id", "ordinal", name="uq_review_session_item_ordinal"),
        UniqueConstraint("session_id", "media_id", name="uq_review_session_item_media"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("review_session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    session: Mapped[ReviewSession] = relationship(back_populates="items")
    media: Mapped[Media] = relationship(back_populates="review_memberships")


class WeightingProfile(Base):
    __tablename__ = "weighting_profile"
    __table_args__ = (
        UniqueConstraint(
            "stable_key",
            "version",
            name="uq_weighting_profile_version",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    stable_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weights: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    default_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1",
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    created_by: Mapped[User | None] = relationship(back_populates="weighting_profiles")
    analysis_runs: Mapped[list[AnalysisRun]] = relationship(back_populates="weighting_profile")


class AnalysisRun(Base):
    __tablename__ = "analysis_run"
    __table_args__ = (Index("ix_analysis_run_created", "created_by_user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    filter_spec: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    report_spec: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    weighting_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("weighting_profile.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    calculation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("analysis_run.id", ondelete="SET NULL"),
        index=True,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    media_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    excluded_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    group_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    effective_criteria: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    warnings: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    context: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    weighting_profile: Mapped[WeightingProfile] = relationship(back_populates="analysis_runs")
    parent_run: Mapped[AnalysisRun | None] = relationship(
        remote_side="AnalysisRun.id",
        back_populates="reruns",
    )
    reruns: Mapped[list[AnalysisRun]] = relationship(back_populates="parent_run")
    created_by: Mapped[User] = relationship(back_populates="analysis_runs")
    members: Mapped[list[AnalysisMember]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )
    results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class AnalysisMember(Base):
    __tablename__ = "analysis_member"
    __table_args__ = (
        UniqueConstraint("run_id", "media_id", name="uq_analysis_member_media"),
        Index("ix_analysis_member_inclusion", "run_id", "included", "exclusion_reason"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_id: Mapped[UUID] = mapped_column(
        ForeignKey("media.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    evaluation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation.id", ondelete="RESTRICT"),
        index=True,
    )
    template_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("evaluation_template.id", ondelete="RESTRICT"),
        index=True,
    )
    evaluation_version: Mapped[int | None] = mapped_column(Integer)
    included: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    exclusion_reason: Mapped[str | None] = mapped_column(String(64), index=True)
    group_keys: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    model_context: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    composite_score: Mapped[float | None] = mapped_column(Float)
    included_criterion_keys: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )

    run: Mapped[AnalysisRun] = relationship(back_populates="members")
    media: Mapped[Media] = relationship(back_populates="analysis_memberships")
    evaluation: Mapped[Evaluation | None] = relationship(back_populates="analysis_memberships")
    score_snapshots: Mapped[list[AnalysisScoreSnapshot]] = relationship(
        back_populates="member",
        cascade="all, delete-orphan",
    )


class AnalysisScoreSnapshot(Base):
    __tablename__ = "analysis_score_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "member_id",
            "criterion_version_id",
            name="uq_analysis_score_criterion",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_member.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("criterion_version.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    score_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("score_revision.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    criterion_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    criterion_label: Mapped[str] = mapped_column(String(256), nullable=False)
    score_state: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[int | None] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    member: Mapped[AnalysisMember] = relationship(back_populates="score_snapshots")


class AnalysisResult(Base):
    __tablename__ = "analysis_result"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "group_hash",
            "criterion_key",
            name="uq_analysis_result_group_criterion",
        ),
        Index("ix_analysis_result_report", "run_id", "criterion_key", "mean"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("analysis_run.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    group_key: Mapped[str] = mapped_column(Text, nullable=False)
    group_label: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    criterion_key: Mapped[str] = mapped_column(String(128), nullable=False)
    criterion_label: Mapped[str] = mapped_column(String(256), nullable=False)
    eligible_count: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_count: Mapped[int] = mapped_column(Integer, nullable=False)
    na_count: Mapped[int] = mapped_column(Integer, nullable=False)
    not_collected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    trash_count: Mapped[int] = mapped_column(Integer, nullable=False)
    coverage: Mapped[float] = mapped_column(Float, nullable=False)
    mean: Mapped[float | None] = mapped_column(Float)
    median: Mapped[float | None] = mapped_column(Float)
    minimum: Mapped[float | None] = mapped_column(Float)
    maximum: Mapped[float | None] = mapped_column(Float)
    q1: Mapped[float | None] = mapped_column(Float)
    q3: Mapped[float | None] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    reference_group_key: Mapped[str | None] = mapped_column(Text)
    difference_from_reference: Mapped[float | None] = mapped_column(Float)
    effect_size: Mapped[float | None] = mapped_column(Float)
    evidence_strength: Mapped[str] = mapped_column(String(32), nullable=False)
    histogram: Mapped[list[object]] = mapped_column(
        json_type,
        nullable=False,
        default=list,
        server_default="[]",
    )
    context: Mapped[dict[str, object]] = mapped_column(
        json_type,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    run: Mapped[AnalysisRun] = relationship(back_populates="results")
