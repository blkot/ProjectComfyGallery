from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from statistics import fmean, median

BOOTSTRAP_SAMPLES = 500


@dataclass(frozen=True, slots=True)
class DistributionSummary:
    eligible_count: int
    scored_count: int
    na_count: int
    not_collected_count: int
    trash_count: int
    coverage: float
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None
    q1: float | None
    q3: float | None
    ci_low: float | None
    ci_high: float | None
    difference_from_reference: float | None
    effect_size: float | None
    evidence_strength: str
    histogram: list[int]


def summarize_distribution(
    values: list[float],
    *,
    eligible_count: int,
    na_count: int,
    not_collected_count: int,
    trash_count: int,
    seed_material: str,
    reference_values: list[float] | None = None,
) -> DistributionSummary:
    scored_count = len(values)
    coverage = scored_count / eligible_count if eligible_count else 0.0
    histogram = [0] * 11
    for value in values:
        bucket = min(10, max(0, round(value)))
        histogram[bucket] += 1
    if not values:
        return DistributionSummary(
            eligible_count=eligible_count,
            scored_count=0,
            na_count=na_count,
            not_collected_count=not_collected_count,
            trash_count=trash_count,
            coverage=coverage,
            mean=None,
            median=None,
            minimum=None,
            maximum=None,
            q1=None,
            q3=None,
            ci_low=None,
            ci_high=None,
            difference_from_reference=None,
            effect_size=None,
            evidence_strength="insufficient",
            histogram=histogram,
        )

    ordered = sorted(values)
    mean_value = fmean(values)
    ci_low, ci_high = bootstrap_mean_interval(values, seed_material=seed_material)
    difference = None
    effect = None
    if reference_values:
        difference = mean_value - fmean(reference_values)
        effect = cliffs_delta(values, reference_values)
    evidence = evidence_strength(
        scored_count=scored_count,
        coverage=coverage,
        ci_low=ci_low,
        ci_high=ci_high,
    )
    return DistributionSummary(
        eligible_count=eligible_count,
        scored_count=scored_count,
        na_count=na_count,
        not_collected_count=not_collected_count,
        trash_count=trash_count,
        coverage=coverage,
        mean=mean_value,
        median=float(median(values)),
        minimum=min(values),
        maximum=max(values),
        q1=quantile(ordered, 0.25),
        q3=quantile(ordered, 0.75),
        ci_low=ci_low,
        ci_high=ci_high,
        difference_from_reference=difference,
        effect_size=effect,
        evidence_strength=evidence,
        histogram=histogram,
    )


def quantile(ordered_values: list[float], probability: float) -> float:
    if not ordered_values:
        raise ValueError("A quantile requires at least one value.")
    if len(ordered_values) == 1:
        return ordered_values[0]
    position = (len(ordered_values) - 1) * probability
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered_values) - 1)
    fraction = position - lower_index
    return ordered_values[lower_index] * (1 - fraction) + ordered_values[upper_index] * fraction


def bootstrap_mean_interval(
    values: list[float],
    *,
    seed_material: str,
    samples: int = BOOTSTRAP_SAMPLES,
) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    seed = int.from_bytes(
        hashlib.sha256(seed_material.encode("utf-8")).digest()[:8],
        byteorder="big",
    )
    generator = random.Random(seed)
    count = len(values)
    means = sorted(
        fmean(values[generator.randrange(count)] for _ in range(count)) for _ in range(samples)
    )
    return quantile(means, 0.025), quantile(means, 0.975)


def cliffs_delta(values: list[float], reference_values: list[float]) -> float | None:
    if not values or not reference_values:
        return None
    greater = 0
    lower = 0
    for value in values:
        for reference in reference_values:
            if value > reference:
                greater += 1
            elif value < reference:
                lower += 1
    return (greater - lower) / (len(values) * len(reference_values))


def evidence_strength(
    *,
    scored_count: int,
    coverage: float,
    ci_low: float,
    ci_high: float,
) -> str:
    if scored_count < 5 or coverage < 0.5:
        return "insufficient"
    if scored_count >= 20 and coverage >= 0.8 and ci_high - ci_low <= 2.0:
        return "stronger"
    return "suggestive"
