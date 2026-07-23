# Analytics Design

**Status:** Accepted

## Analytical goal

The application identifies score tendencies associated with checkpoints, checkpoint pairs, LoRAs, LoRA training steps, and model combinations within a user-selected collection of completed evaluations.

It does not attempt to prove a universal model ranking.

Preferred language:

- “Associated with”
- “Shows a tendency”
- “Within the selected media”
- “The observed score distribution”

Avoid:

- “Caused”
- “Objectively better”
- “Best model” without explicit user interpretation
- “Official benchmark score”

## Population selection

The user defines the population through filters:

- Architecture family.
- Pipeline pattern.
- Selected checkpoint/LoRA artifacts or comparison set.
- Media type.
- Evaluation template/module.
- Collection, tag, source folder, date, or other extracted metadata.
- Optional sampler, seed, prompt, dimensions, or configuration filters.

Only Complete evaluations enter by default. Trash is excluded by default.

Prompts:

- Are visible during evaluation.
- Remain searchable/filterable metadata.
- Are not used for default balancing, matching, or adjustment.

This is intentional: the user wants real-usage involvement profiles rather than laboratory controls.

## MVP report catalog

### 1. Checkpoint profile

Question:

> What score tendencies appear when each checkpoint is involved in the selected media?

Boundaries:

- Respect architecture family.
- Respect pipeline pattern.
- Separate usage slots by default.
- Offer an explicitly labeled any-role view when useful.

### 2. Checkpoint-pair profile

Question:

> What tendencies appear for each ordered checkpoint pair?

Examples:

- Wan 2.2 high-noise + low-noise.
- Krea 2 first-pass + second-pass.

Pair order is part of the group key.

### 3. LoRA profile

Question:

> What tendencies appear when an individual LoRA is involved?

A media using several LoRAs contributes to each individual involvement profile. Counts and common co-occurrences are shown to avoid hiding overlap.

### 4. LoRA training-series trend

Question:

> How do score distributions change across adapter training steps?

Requirements:

- Group within one confirmed/inferred series.
- Treat step as numeric for plotting.
- Show per-step sample count and uncertainty.
- Do not assume the relationship is linear or that later steps are better.

### 5. Checkpoint-by-LoRA matrix

Question:

> How does a LoRA’s observed score profile vary across checkpoints?

Requirements:

- Sparse cells remain visible as insufficient data.
- Cell counts and coverage are always accessible.
- Pipeline/slot boundaries remain applied.

### 6. LoRA-combination profile

Question:

> What tendencies appear for exact sets of LoRAs used together?

The group key is an order-independent set of canonical/historical LoRA identities. Strength values are retained but do not split MVP groups unless the user filters them explicitly.

## Non-report metadata

The following remain filterable and visible but have no dedicated MVP report:

- Prompt text/fingerprint.
- Seed.
- Image/video dimensions.
- Sampler and scheduler.
- Single- or multi-stage sampler recipe.
- Step count.
- LoRA strength.
- Precision/quantization.

This preserves future analytical value without diluting the MVP’s model focus.

## Statistics

Each group/criterion should provide:

- Eligible media count.
- Scored count.
- N/A count and coverage percentage.
- Trash count outside the default dataset when relevant.
- Mean.
- Median.
- Minimum/maximum where useful.
- Interquartile range.
- Score histogram/distribution.
- 95% bootstrap confidence interval.
- Difference from a selected reference.
- Effect size against a selected reference.

Phase 5 uses **Cliff's delta** against the selected reference. It is appropriate for
bounded, ordinal-like manual scores and makes no normal-distribution assumption. The
report explains direction and magnitude in plain language.

Scores are bounded and subjectively assigned. Median, distribution, and coverage must remain visible even when means are presented.

## Evidence language

The UI may label evidence as:

- **Insufficient**
- **Suggestive**
- **Stronger evidence**

V1 operational thresholds are:

- Insufficient when scored count is below 5 or coverage is below 50%.
- Stronger evidence at 20 or more scored media, at least 80% coverage, and a
  bootstrap-mean interval no wider than 2 points.
- Suggestive for other non-empty results.

The engine also warns about major group-size imbalance and identity uncertainty.
Future threshold calibration increments the calculation version rather than changing
saved results.

These labels describe evidence strength, not model quality.

## Co-occurrence and confounding context

Reports do not mathematically “correct” the historical dataset by default. They do show context such as:

- Common checkpoint/LoRA co-occurrences.
- Group sample imbalance.
- Pipeline-pattern differences.
- Slot differences.
- Major registry-identity uncertainty.
- Different template/criterion coverage.

Example:

> “Most media involving Checkpoint A also use LoRA X; treat the checkpoint-only tendency as contextual.”

The user can narrow filters when a more focused population is desired.

## Composite scores

### Source of truth

Raw criterion values are authoritative.

### Calculation

For scored criteria \(i\) with weight \(w_i\) and score \(s_i\):

```text
composite = sum(w_i * s_i) / sum(w_i)
```

N/A and not-collected criteria are excluded from both numerator and denominator. The report must show which criteria contributed.

### Profiles

- Equal weight is default.
- Profile versions are immutable.
- A report records profile ID/version.
- Users may view criteria independently instead of using a composite.
- Sensitivity views may compare results across profiles without changing evaluation data.

## Template-version compatibility

Criterion-specific analysis:

- Uses all evaluations that collected that criterion.
- Shows coverage and template-version distribution.

Composite analysis across versions:

- Defaults to criteria shared across the selected templates.
- Does not impute missing historical criteria.
- Shows the effective criterion set and coverage.

Users may explicitly narrow to one template version.

## Live exploration

Live mode:

- Recalculates as filters, scores, or registry links change.
- May use cached aggregates.
- Clearly indicates stale/recalculating state.
- Is not a durable historical result.

## Saved analysis runs

Saving freezes:

- Exact media IDs.
- Exact evaluation/score revision IDs.
- Filters and exclusions.
- Report factor/group keys.
- Architecture/pipeline boundaries.
- Criteria/template versions.
- Weighting profile.
- Calculation software version.
- Registry-identity evidence used.
- Result payload and warnings.

Saved runs never silently change.

“Rerun with current data” creates a new run linked to the previous run. This supports longitudinal comparison without rewriting history.

## Performance

- Filtering/grouping should execute in PostgreSQL where practical.
- Heavy bootstrap/report computation may run in the worker.
- Results are stored as structured JSON plus queryable summary columns.
- Large matrices require pagination/virtualization.
- A saved report should remain viewable even after current registry corrections.

## Interpretation guardrails

- No automatic global winner.
- No hidden removal of outliers.
- No score imputation.
- No automatic prompt matching.
- No pooling of incompatible architecture/pipeline cohorts by default.
- No treating filename-inferred identity as hash certainty.
- Every chart exposes underlying media through drill-down.
