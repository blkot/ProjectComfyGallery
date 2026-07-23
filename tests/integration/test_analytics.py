from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from comfy_gallery_core.analytics.service import (
    compute_report,
    ensure_equal_weight_profile,
    load_analysis_population,
    save_analysis_run,
)
from comfy_gallery_core.db.base import Base
from comfy_gallery_core.db.models import (
    AnalysisRun,
    Media,
    ModelArtifact,
    ModelReference,
    ModelUsage,
    User,
    WorkflowSnapshot,
)
from comfy_gallery_core.evaluation.catalog import ensure_evaluation_catalog
from comfy_gallery_core.evaluation.service import (
    ensure_media_evaluations,
    load_evaluation,
    update_score,
)


async def test_saved_run_is_immutable_and_rerun_uses_current_score_revision() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        user = User(
            username="analyst",
            username_normalized="analyst",
            password_hash="test",
        )
        media = Media(kind="image", status="ready")
        session.add_all([user, media])
        await session.flush()
        await ensure_evaluation_catalog(session)
        evaluation = (
            await ensure_media_evaluations(
                session,
                media=media,
                reviewer_user_id=user.id,
                optional_modules=set(),
            )
        )[0]
        await session.commit()
        evaluation = await load_evaluation(session, evaluation.id)
        for item in evaluation.template.items:
            evaluation = await update_score(
                session,
                evaluation=evaluation,
                criterion_version_id=item.criterion_version_id,
                expected_version=evaluation.version,
                state="scored",
                value=4,
                na_reason=None,
                user_id=user.id,
            )

        snapshot = WorkflowSnapshot(
            media_id=media.id,
            reader_name="test",
            reader_version="1",
            source_carrier="test",
            evidence_sha256="a" * 64,
            raw_metadata={},
            api_prompt_status="absent",
            visual_workflow_status="absent",
            parse_status="parsed",
            issue_details={},
        )
        artifact = ModelArtifact(
            artifact_type="checkpoint",
            display_name="Krea Turbo",
            provider="test",
            identity_state="confirmed",
            availability="present",
            enrichment_state="matched",
            architecture_family="Krea 2",
        )
        session.add_all([snapshot, artifact])
        await session.flush()
        reference = ModelReference(
            artifact_id=artifact.id,
            reference_type="checkpoint",
            raw_value="krea-turbo.safetensors",
            normalized_value="krea-turbo.safetensors",
            availability="present",
            resolution_state="resolved",
            occurrence_count=1,
        )
        session.add(reference)
        await session.flush()
        session.add(
            ModelUsage(
                snapshot_id=snapshot.id,
                model_reference_id=reference.id,
                artifact_id=artifact.id,
                observation_type="checkpoint_reference",
                pipeline_pattern="single_pass",
                slot="single",
                usage_order=0,
                confidence=1,
                evidence={},
            )
        )
        await session.commit()

        profile = await ensure_equal_weight_profile(session)
        candidates = await load_analysis_population(session, {"module": "core"})
        first_computation = compute_report(
            candidates,
            {"report_type": "checkpoint"},
            profile,
        )
        first_run = await save_analysis_run(
            session,
            computation=first_computation,
            filter_spec={"module": "core"},
            report_spec={"report_type": "checkpoint"},
            weighting_profile=profile,
            user=user,
            title="Initial",
        )
        first_result_mean = next(
            result.mean
            for result in first_computation.results
            if result.criterion_key == "__composite__"
        )
        assert first_result_mean == 4

        evaluation = await load_evaluation(session, evaluation.id)
        evaluation = await update_score(
            session,
            evaluation=evaluation,
            criterion_version_id=evaluation.template.items[0].criterion_version_id,
            expected_version=evaluation.version,
            state="scored",
            value=10,
            na_reason=None,
            user_id=user.id,
        )
        current_candidates = await load_analysis_population(session, {"module": "core"})
        second_computation = compute_report(
            current_candidates,
            {"report_type": "checkpoint"},
            profile,
        )
        second_run = await save_analysis_run(
            session,
            computation=second_computation,
            filter_spec={"module": "core"},
            report_spec={"report_type": "checkpoint"},
            weighting_profile=profile,
            user=user,
            title="Rerun",
            parent_run=first_run,
        )

        await session.refresh(first_run, attribute_names=["results"])
        await session.refresh(second_run, attribute_names=["results"])
        original_mean = next(
            result.mean for result in first_run.results if result.criterion_key == "__composite__"
        )
        rerun_mean = next(
            result.mean for result in second_run.results if result.criterion_key == "__composite__"
        )
        assert original_mean == 4
        assert rerun_mean == 5
        assert second_run.parent_run_id == first_run.id
        assert (
            len(list(await session.scalars(select(AnalysisRun).order_by(AnalysisRun.created_at))))
            == 2
        )

    await engine.dispose()
