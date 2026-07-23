from comfy_gallery_core.analytics.statistics import (
    bootstrap_mean_interval,
    cliffs_delta,
    evidence_strength,
    quantile,
    summarize_distribution,
)


def test_distribution_summary_is_deterministic_and_keeps_bounded_histogram() -> None:
    first = summarize_distribution(
        [0, 3, 7, 10],
        eligible_count=6,
        na_count=1,
        not_collected_count=1,
        trash_count=2,
        seed_material="stable",
    )
    second = summarize_distribution(
        [0, 3, 7, 10],
        eligible_count=6,
        na_count=1,
        not_collected_count=1,
        trash_count=2,
        seed_material="stable",
    )

    assert first == second
    assert first.mean == 5
    assert first.median == 5
    assert first.q1 == 2.25
    assert first.q3 == 7.75
    assert first.coverage == 4 / 6
    assert first.histogram[0] == 1
    assert first.histogram[10] == 1
    assert sum(first.histogram) == 4


def test_reference_statistics_explain_direction_without_declaring_a_winner() -> None:
    summary = summarize_distribution(
        [7, 8, 9],
        eligible_count=3,
        na_count=0,
        not_collected_count=0,
        trash_count=0,
        seed_material="reference",
        reference_values=[1, 2, 3],
    )

    assert summary.difference_from_reference == 6
    assert summary.effect_size == 1
    assert cliffs_delta([1, 2, 3], [7, 8, 9]) == -1
    assert cliffs_delta([1, 2], [1, 2]) == 0


def test_quantile_bootstrap_and_evidence_boundaries() -> None:
    assert quantile([5], 0.25) == 5
    assert bootstrap_mean_interval([4], seed_material="one") == (4, 4)
    assert evidence_strength(scored_count=4, coverage=1, ci_low=4, ci_high=4) == ("insufficient")
    assert evidence_strength(scored_count=10, coverage=0.9, ci_low=4, ci_high=5) == ("suggestive")
    assert evidence_strength(scored_count=20, coverage=0.8, ci_low=4, ci_high=6) == ("stronger")
