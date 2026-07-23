from uuid import uuid4

from comfy_gallery_core.analytics.service import (
    AnalysisCandidate,
    ModelUse,
    ScorePoint,
    SeriesMembership,
    compute_report,
)
from comfy_gallery_core.db.models import WeightingProfile


def _candidate() -> AnalysisCandidate:
    series = SeriesMembership(
        series_id=uuid4(),
        series_name="Character training",
        training_step=3500,
    )
    uses = (
        ModelUse(
            reference_id=uuid4(),
            artifact_id=uuid4(),
            identity_key="artifact:high",
            identity_label="Krea Raw",
            identity_state="confirmed",
            observation_type="checkpoint_reference",
            architecture_family="Krea 2",
            pipeline_pattern="dual_pass",
            slot="first_pass",
            usage_order=0,
            confidence=1,
        ),
        ModelUse(
            reference_id=uuid4(),
            artifact_id=uuid4(),
            identity_key="artifact:turbo",
            identity_label="Krea Turbo",
            identity_state="confirmed",
            observation_type="checkpoint_reference",
            architecture_family="Krea 2",
            pipeline_pattern="dual_pass",
            slot="second_pass",
            usage_order=1,
            confidence=1,
        ),
        ModelUse(
            reference_id=uuid4(),
            artifact_id=uuid4(),
            identity_key="artifact:lora-a",
            identity_label="Character 3500",
            identity_state="confirmed",
            observation_type="lora_reference",
            architecture_family="Unknown architecture",
            pipeline_pattern="dual_pass",
            slot="adapter",
            usage_order=2,
            confidence=1,
            series=(series,),
        ),
        ModelUse(
            reference_id=uuid4(),
            artifact_id=uuid4(),
            identity_key="artifact:lora-b",
            identity_label="Style",
            identity_state="confirmed",
            observation_type="lora_reference",
            architecture_family="Unknown architecture",
            pipeline_pattern="dual_pass",
            slot="adapter",
            usage_order=3,
            confidence=1,
        ),
    )
    score = ScorePoint(
        criterion_version_id=uuid4(),
        score_revision_id=uuid4(),
        key="visual_quality",
        label="Visual quality",
        state="scored",
        value=8,
    )
    return AnalysisCandidate(
        media_id=uuid4(),
        media_kind="image",
        evaluation_id=uuid4(),
        template_id=uuid4(),
        template_version=1,
        evaluation_version=2,
        progress_state="complete",
        is_trash=False,
        template_criteria=frozenset({"visual_quality"}),
        scores={"visual_quality": score},
        model_uses=uses,
    )


def _profile() -> WeightingProfile:
    return WeightingProfile(
        stable_key="equal",
        version=1,
        name="Equal",
        weights={},
        default_weight=1,
        is_builtin=True,
    )


def test_all_six_reports_produce_boundary_aware_groups() -> None:
    expected_groups = {
        "checkpoint": 2,
        "checkpoint_pair": 1,
        "lora": 2,
        "lora_training_series": 1,
        "checkpoint_lora_matrix": 4,
        "lora_combination": 1,
    }
    for report_type, group_count in expected_groups.items():
        report = compute_report(
            [_candidate()],
            {"report_type": report_type},
            _profile(),
        )

        assert report.media_count == 1
        assert report.group_count == group_count
        assert (
            len([result for result in report.results if result.criterion_key == "__composite__"])
            == group_count
        )
        assert all(
            result.group.dimensions.get("architecture_family") == "Krea 2"
            for result in report.results
        )


def test_shared_criteria_never_impute_missing_values_as_zero() -> None:
    first = _candidate()
    second = AnalysisCandidate(
        media_id=uuid4(),
        media_kind="image",
        evaluation_id=uuid4(),
        template_id=uuid4(),
        template_version=2,
        evaluation_version=4,
        progress_state="complete",
        is_trash=False,
        template_criteria=frozenset({"visual_quality", "new_criterion"}),
        scores={
            "visual_quality": ScorePoint(
                criterion_version_id=uuid4(),
                score_revision_id=uuid4(),
                key="visual_quality",
                label="Visual quality",
                state="na",
                value=None,
            )
        },
        model_uses=first.model_uses,
    )

    report = compute_report(
        [first, second],
        {"report_type": "checkpoint", "compatibility_mode": "shared"},
        _profile(),
    )
    result = next(
        item
        for item in report.results
        if item.criterion_key == "__composite__"
        and item.group.dimensions.get("slot") == "first_pass"
    )

    assert report.effective_criteria == [{"key": "visual_quality", "label": "Visual quality"}]
    assert result.eligible_count == 2
    assert result.scored_count == 1
    assert result.na_count == 1
    assert result.mean == 8
