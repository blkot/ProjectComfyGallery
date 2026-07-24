# Phase 5 Model-Focused Analytics

**Status:** Implemented and verified on 2026-07-24
**Release:** `0.1.0-rc.4`

## Outcome

Phase 5 turns completed manual evaluations into observational checkpoint and LoRA
reports. The implementation describes score tendencies inside a user-selected
population. It does not perform prompt matching, claim causality, rank a universal
winner, or treat a two-model pipeline as inherently better than a one-model pipeline.

Every grouping key retains the compatibility context needed for interpretation:

- architecture family;
- pipeline pattern;
- checkpoint usage slot unless the user explicitly chooses an any-role view;
- ordered checkpoint position for pair reports;
- canonical artifact identity or exact historical workflow reference;
- LoRA training-series identity and numeric step where applicable.

This lets a Wan 2.1 single-model workflow remain separate from a Wan 2.2 high/low
noise pair, while Krea 2 first-pass raw and second-pass turbo-lineage roles also remain
visible.

## Database and migration

Alembic revision `0006_model_analytics` adds:

- `weighting_profile`;
- `analysis_run`;
- `analysis_member`;
- `analysis_score_snapshot`;
- `analysis_result`.

The migration seeds a deterministic, immutable Equal weight V1 profile. Custom
profiles are versioned instead of edited in place.

A saved run freezes:

- the filter and report specification;
- weighting-profile ID/version;
- calculation software version;
- exact media, evaluation, template, and evaluation version;
- the current score revision for every contributing criterion;
- scored/N/A state, value, label, and applied weight;
- inclusion/exclusion reason;
- model-use identity, confidence, architecture, pipeline, slot, and series evidence;
- exact group keys;
- statistics, histogram, evidence label, context, and warnings.

Changing a score or registry link cannot alter these rows. “Rerun with current data”
creates a new `analysis_run` whose `parent_run_id` points to the earlier snapshot.

## Population and score semantics

The population builder supports:

- core or character evaluation module;
- image/video kind;
- exact template versions;
- collection, tag, and source directory;
- architecture family and pipeline pattern;
- usage slots and exact artifacts;
- user-managed comparison group;
- LoRA training series;
- explicit Trash inclusion.

Only Complete evaluations are eligible by default. Trash is excluded by default.
Not evaluated, incomplete, Trash, and factor-not-observed media retain explicit
exclusion reasons in saved runs instead of disappearing or becoming score zero.

For cross-template composites, the default effective criterion set is the
intersection shared by selected templates. Optional available-criteria mode uses the
union with a visible warning.

For scored criteria \(i\):

```text
composite = sum(weight_i * score_i) / sum(weight_i)
```

N/A and not-collected criteria are excluded from both sums. A real score of zero
remains zero.

## MVP reports

The same calculation engine provides all six accepted reports:

| Report | Group behavior |
|---|---|
| Checkpoint profile | One group per checkpoint, architecture, pipeline, and slot |
| Ordered checkpoint pair | Exactly two checkpoint uses ordered by usage position/slot |
| LoRA profile | One involvement group per LoRA; multi-LoRA media may contribute to several groups |
| LoRA training steps | Series ID plus numeric step, architecture, and pipeline |
| Checkpoint × LoRA | Checkpoint/slot and LoRA cross-product with sparse cells preserved |
| Exact LoRA combination | Order-independent set of LoRA identities within architecture/pipeline context |

Historical/deleted workflow-only models remain usable as exact reference identities
with uncertainty context. Filename inference never becomes hash certainty.

## Statistics and evidence language

For each group and raw criterion, plus the weighted composite, the engine stores:

- eligible, scored, N/A, not-collected, and Trash counts;
- coverage;
- mean, median, minimum, maximum, Q1, and Q3;
- an integer score histogram from 0 through 10;
- a deterministic 95% percentile bootstrap interval for the mean using 500 resamples;
- difference from a selected reference mean;
- Cliff's delta against the selected reference.

Cliff's delta was selected because the manual scores are ordinal-like, bounded, and
need no normal-distribution assumption. It describes how often an item from one group
scores above versus below an item from the reference. The UI reports its direction
and conventional magnitude as a tendency, never as a winner.

Initial V1 evidence labels are operational presentation thresholds:

- **Insufficient:** fewer than 5 scored media or coverage below 50%.
- **Stronger evidence:** at least 20 scored media, at least 80% coverage, and a
  bootstrap interval no wider than 2 score points.
- **Suggestive:** every other non-empty result.

These labels describe confidence in the observed distribution, not model quality.
Future calibration must increment the calculation version so saved runs remain
interpretable.

Bootstrap seeds derive from report/group/criterion keys. The same frozen inputs
therefore produce the same interval without storing random state.

## API

Phase 5 implements:

```text
GET    /api/v1/analysis/options
POST   /api/v1/analysis/previews
GET    /api/v1/analysis/runs
POST   /api/v1/analysis/runs
GET    /api/v1/analysis/runs/:id
POST   /api/v1/analysis/runs/:id/rerun
GET    /api/v1/analysis/runs/:id/media

GET    /api/v1/weighting-profiles
POST   /api/v1/weighting-profiles
POST   /api/v1/weighting-profiles/:id/versions
```

Database population loading remains asynchronous. CPU bootstrap/group computation
runs in a worker thread so it does not block the FastAPI event loop on the J4125
deployment target. Durable heavy-job execution remains an optimization for larger
future populations.

## Frontend

`/analysis` provides:

- six question-oriented report choices;
- compatible population filters;
- shared/available criterion mode;
- versioned weighting-profile creation;
- live preview;
- reference-group selection;
- immutable save;
- saved-run history.

`/analysis/:runId` renders only stored snapshot results and provides:

- linked rerun with current data;
- parent-run navigation;
- composite or per-criterion selection;
- counts, coverage, histogram, mean, median, quartiles, and uncertainty;
- plain-language effect-size and evidence explanations;
- non-linear LoRA step plot;
- sparse checkpoint × LoRA matrix;
- media drill-down back to the Library.

The route is lazy-loaded and uses no large chart dependency. SVG, semantic tables,
and CSS provide a compact bundle and exact-value equivalents for visualizations.

## Verification

### Automated

The complete check suite passes:

- Ruff lint and formatting;
- strict mypy across 56 Python source files;
- 41 pytest tests;
- ESLint and TypeScript project checks;
- 10 Vitest tests across three frontend test files;
- production Vite build with the analysis route emitted as a separate lazy chunk.

Phase 5 regressions cover:

- deterministic bootstrap, quantiles, histograms, evidence thresholds, and
  Cliff's delta;
- all six grouping strategies;
- architecture/pipeline boundaries and ordered checkpoint pairs;
- shared-criterion compatibility with N/A never becoming zero;
- immutable saved results after a score revision;
- linked rerun using the new current score revision.

### Migration

A clean PostgreSQL database upgraded through revisions 0001–0006. `alembic check`
reported no schema drift and `alembic current` reported
`0006_model_analytics (head)`. No migration requires network access or ComfyUI.

### Live Docker, ComfyUI, and browser

The production Compose stack was validated with the private corpus and the live
ComfyUI/LoRA Manager endpoint:

- 14 media imported with zero failures;
- 14 complete core evaluations;
- node and model synchronizations succeeded;
- 55 workflow model usages;
- 419 model artifacts;
- checkpoint profiles rendered with architecture/pipeline/slot boundaries;
- local `Krea2_guzong_lora_v2` parsed and plotted at numeric step 3500;
- an immutable run saved 12 score-revision snapshots and seven stored result rows;
- media drill-down opened the exact frozen member;
- rerun created a second run linked to its parent;
- API/worker logs contained no 500 responses or tracebacks.

The browser check also caught and fixed overlapping invisible report-radio hit areas
before completion.

### NAS portability

Fresh backend and frontend production images built and loaded successfully for
`linux/amd64`, matching the x86 J4125 NAS target. The worker remains one process and
one thread; the analytics engine has no CUDA or GPU dependency.

## Phase boundary

Phase 5 is observational and manual-evaluation driven. Automated GPU benchmarks,
causal adjustment, prompt balancing, dedicated sampler/strength reports, portable
exports, and the future ComfyUI custom-node ingestion API remain outside this phase.
