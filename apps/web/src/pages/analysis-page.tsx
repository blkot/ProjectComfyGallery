import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  apiRequest,
  type AnalysisFilter,
  type AnalysisMedia,
  type AnalysisOptions,
  type AnalysisReport,
  type AnalysisReportType,
  type AnalysisResult,
  type AnalysisRun,
  type AnalysisRunSummary,
  type AnalysisSpec,
  type Collection,
  type SourceRoot,
  type WeightingProfile,
} from "../lib/api";
import {
  criterionResults,
  evidenceLabel,
  explainEffect,
  formatInterval,
  formatScore,
} from "../lib/analysis";
import { formatDate, titleCase } from "../lib/format";

const REPORTS: Array<{
  id: AnalysisReportType;
  label: string;
  question: string;
}> = [
  {
    id: "checkpoint",
    label: "Checkpoint profile",
    question: "What tendencies appear when each checkpoint is involved?",
  },
  {
    id: "checkpoint_pair",
    label: "Ordered checkpoint pairs",
    question: "How do high/low-noise or first/second-pass pairs behave?",
  },
  {
    id: "lora",
    label: "LoRA profile",
    question: "What tendencies appear when each individual LoRA is involved?",
  },
  {
    id: "lora_training_series",
    label: "LoRA training steps",
    question: "How does a local adapter series change across training steps?",
  },
  {
    id: "checkpoint_lora_matrix",
    label: "Checkpoint × LoRA",
    question: "How does each LoRA vary across checkpoint contexts?",
  },
  {
    id: "lora_combination",
    label: "Exact LoRA combinations",
    question: "What tendencies appear for exact sets of LoRAs used together?",
  },
];

const EMPTY_FILTER: AnalysisFilter = {
  module: "core",
  media_kind: null,
  template_ids: [],
  collection_id: null,
  tag_id: null,
  source_root_id: null,
  architecture_family: null,
  pipeline_pattern: null,
  slots: [],
  artifact_ids: [],
  comparison_group_id: null,
  lora_series_id: null,
  include_trash: false,
};

const EMPTY_SPEC: AnalysisSpec = {
  report_type: "checkpoint",
  criterion_keys: [],
  compatibility_mode: "shared",
  any_role: false,
  reference_group_key: null,
  weighting_profile_id: null,
};

export function AnalysisPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<AnalysisFilter>(EMPTY_FILTER);
  const [spec, setSpec] = useState<AnalysisSpec>(EMPTY_SPEC);
  const [preview, setPreview] = useState<AnalysisReport | null>(null);
  const [title, setTitle] = useState("");
  const [criterionKey, setCriterionKey] = useState("__composite__");
  const [drillGroup, setDrillGroup] = useState<string | null>(null);
  const [showProfileForm, setShowProfileForm] = useState(false);

  const options = useQuery({
    queryKey: ["analysis-options"],
    queryFn: () => apiRequest<AnalysisOptions>("/api/v1/analysis/options"),
  });
  const profiles = useQuery({
    queryKey: ["weighting-profiles"],
    queryFn: () =>
      apiRequest<WeightingProfile[]>("/api/v1/weighting-profiles"),
  });
  const runs = useQuery({
    queryKey: ["analysis-runs"],
    queryFn: () => apiRequest<AnalysisRunSummary[]>("/api/v1/analysis/runs"),
  });
  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: () => apiRequest<Collection[]>("/api/v1/collections"),
  });
  const roots = useQuery({
    queryKey: ["source-roots"],
    queryFn: () => apiRequest<SourceRoot[]>("/api/v1/source-roots"),
  });
  const savedRun = useQuery({
    queryKey: ["analysis-run", runId],
    queryFn: () => apiRequest<AnalysisRun>(`/api/v1/analysis/runs/${runId}`),
    enabled: Boolean(runId),
  });
  const previewMutation = useMutation({
    mutationFn: () =>
      apiRequest<AnalysisReport>("/api/v1/analysis/previews", {
        method: "POST",
        body: JSON.stringify({ filter, spec }),
      }),
    onSuccess: (report) => {
      setPreview(report);
      setCriterionKey("__composite__");
    },
  });
  const saveMutation = useMutation({
    mutationFn: () =>
      apiRequest<AnalysisRun>("/api/v1/analysis/runs", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim() || `${titleCase(spec.report_type)} analysis`,
          filter,
          spec,
        }),
      }),
    onSuccess: async (run) => {
      await queryClient.invalidateQueries({ queryKey: ["analysis-runs"] });
      navigate(`/analysis/${run.id}`);
    },
  });
  const rerunMutation = useMutation({
    mutationFn: () =>
      apiRequest<AnalysisRun>(`/api/v1/analysis/runs/${runId}/rerun`, {
        method: "POST",
      }),
    onSuccess: async (run) => {
      await queryClient.invalidateQueries({ queryKey: ["analysis-runs"] });
      navigate(`/analysis/${run.id}`);
    },
  });
  const media = useQuery({
    queryKey: ["analysis-media", runId, drillGroup],
    queryFn: () =>
      apiRequest<AnalysisMedia[]>(
        `/api/v1/analysis/runs/${runId}/media?group_key=${encodeURIComponent(drillGroup ?? "")}`,
      ),
    enabled: Boolean(runId && drillGroup),
  });

  const report = savedRun.data ?? preview;
  const visibleResults = useMemo(
    () => criterionResults(report?.results ?? [], criterionKey),
    [criterionKey, report?.results],
  );
  const criteria = [
    { key: "__composite__", label: "Weighted composite" },
    ...(report?.effective_criteria ?? []),
  ];
  const isSaved = Boolean(savedRun.data);

  return (
    <main className="page analysis-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Observational model analytics · Phase 5</p>
          <h1>{savedRun.data?.title ?? "Analysis lab"}</h1>
          <p className="muted">
            Find checkpoint and LoRA tendencies inside your own completed reviews.
            Results describe the selected media—not a universal winner or causal benchmark.
          </p>
        </div>
        {isSaved ? (
          <div className="analysis-header-actions">
            <Link className="secondary-button" to="/analysis">
              New analysis
            </Link>
            <button
              className="primary-button"
              type="button"
              disabled={rerunMutation.isPending}
              onClick={() => rerunMutation.mutate()}
            >
              {rerunMutation.isPending ? "Recalculating…" : "Rerun with current data"}
            </button>
          </div>
        ) : null}
      </header>

      {!savedRun.data ? (
        <section className="analysis-builder">
          <form
            className="panel analysis-config"
            onSubmit={(event) => {
              event.preventDefault();
              previewMutation.mutate();
            }}
          >
            <div className="section-heading">
              <div>
                <p className="kicker">1 · Question</p>
                <h2>Choose a report</h2>
              </div>
            </div>
            <div className="report-picker">
              {REPORTS.map((item) => (
                <label
                  className={`report-choice ${spec.report_type === item.id ? "selected" : ""}`}
                  key={item.id}
                >
                  <input
                    type="radio"
                    name="report"
                    checked={spec.report_type === item.id}
                    onChange={() =>
                      setSpec((current) => ({
                        ...current,
                        report_type: item.id,
                        reference_group_key: null,
                      }))
                    }
                  />
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.question}</small>
                  </span>
                </label>
              ))}
            </div>

            <div className="analysis-filter-heading">
              <p className="kicker">2 · Population</p>
              <h2>Keep comparisons compatible</h2>
              <p className="muted">
                Architecture, pipeline, and usage slot remain part of every group key even
                when these filters are left broad.
              </p>
            </div>
            <div className="analysis-filter-grid">
              <SelectField
                label="Media"
                value={filter.media_kind ?? ""}
                options={[
                  { id: "", label: "Images and videos" },
                  { id: "image", label: "Images" },
                  { id: "video", label: "Videos" },
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    media_kind: (value || null) as AnalysisFilter["media_kind"],
                  }))
                }
              />
              <SelectField
                label="Evaluation module"
                value={filter.module}
                options={[
                  { id: "core", label: "Core quality" },
                  { id: "character", label: "Character identity" },
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    module: value as AnalysisFilter["module"],
                  }))
                }
              />
              <SelectField
                label="Architecture"
                value={filter.architecture_family ?? ""}
                options={[
                  { id: "", label: "All (still separated in results)" },
                  ...(options.data?.architecture_families.map((value) => ({
                    id: value,
                    label: value,
                  })) ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    architecture_family: value || null,
                  }))
                }
              />
              <SelectField
                label="Pipeline"
                value={filter.pipeline_pattern ?? ""}
                options={[
                  { id: "", label: "All (still separated in results)" },
                  ...(options.data?.pipeline_patterns.map((value) => ({
                    id: value,
                    label: titleCase(value),
                  })) ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    pipeline_pattern: value || null,
                  }))
                }
              />
              <SelectField
                label="Comparison set"
                value={filter.comparison_group_id ?? ""}
                options={[
                  { id: "", label: "All registered models" },
                  ...(options.data?.comparison_groups ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    comparison_group_id: value || null,
                  }))
                }
              />
              <SelectField
                label="LoRA training series"
                value={filter.lora_series_id ?? ""}
                options={[
                  { id: "", label: "Any series" },
                  ...(options.data?.lora_series ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    lora_series_id: value || null,
                  }))
                }
              />
              <SelectField
                label="Collection"
                value={filter.collection_id ?? ""}
                options={[
                  { id: "", label: "Any collection" },
                  ...(collections.data?.map((item) => ({
                    id: item.id,
                    label: item.name,
                  })) ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    collection_id: value || null,
                  }))
                }
              />
              <SelectField
                label="Source directory"
                value={filter.source_root_id ?? ""}
                options={[
                  { id: "", label: "Any source" },
                  ...(roots.data?.map((item) => ({
                    id: item.id,
                    label: item.name,
                  })) ?? []),
                ]}
                onChange={(value) =>
                  setFilter((current) => ({
                    ...current,
                    source_root_id: value || null,
                  }))
                }
              />
              <SelectField
                label="Weighting profile"
                value={spec.weighting_profile_id ?? ""}
                options={[
                  { id: "", label: "Equal weight" },
                  ...(profiles.data
                    ?.filter((item) => !item.is_builtin)
                    .map((item) => ({
                      id: item.id,
                      label: `${item.name} v${item.version}`,
                    })) ?? []),
                ]}
                onChange={(value) =>
                  setSpec((current) => ({
                    ...current,
                    weighting_profile_id: value || null,
                  }))
                }
              />
            </div>
            <div className="analysis-toggle-row">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={filter.include_trash}
                  onChange={(event) =>
                    setFilter((current) => ({
                      ...current,
                      include_trash: event.target.checked,
                    }))
                  }
                />
                Include Trash in the eligible population
              </label>
              {spec.report_type === "checkpoint" ? (
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={spec.any_role}
                    onChange={(event) =>
                      setSpec((current) => ({
                        ...current,
                        any_role: event.target.checked,
                      }))
                    }
                  />
                  Combine checkpoint usage slots (any-role view)
                </label>
              ) : null}
            </div>
            <details className="analysis-advanced">
              <summary>Criteria compatibility and custom weights</summary>
              <label>
                Cross-template composite
                <select
                  value={spec.compatibility_mode}
                  onChange={(event) =>
                    setSpec((current) => ({
                      ...current,
                      compatibility_mode: event.target
                        .value as AnalysisSpec["compatibility_mode"],
                    }))
                  }
                >
                  <option value="shared">Shared criteria only (recommended)</option>
                  <option value="available">All available criteria</option>
                </select>
              </label>
              <p className="muted small-copy">
                Shared mode compares the same criterion set across template versions.
                Available mode never fills missing values with zero, but composites may
                contain different criteria.
              </p>
              <button
                className="text-button inline-text-button"
                type="button"
                onClick={() => setShowProfileForm((value) => !value)}
              >
                {showProfileForm ? "Close weight profile editor" : "Create a weight profile"}
              </button>
              {showProfileForm ? (
                <WeightProfileForm
                  criteria={options.data?.criteria ?? []}
                  onCreated={async (profile) => {
                    await queryClient.invalidateQueries({
                      queryKey: ["weighting-profiles"],
                    });
                    setSpec((current) => ({
                      ...current,
                      weighting_profile_id: profile.id,
                    }));
                    setShowProfileForm(false);
                  }}
                />
              ) : null}
            </details>
            {previewMutation.error ? (
              <p className="notice error-notice" role="alert">
                {previewMutation.error.message}
              </p>
            ) : null}
            <button
              className="primary-button analysis-preview-button"
              type="submit"
              disabled={previewMutation.isPending}
            >
              {previewMutation.isPending ? "Calculating distributions…" : "Preview analysis"}
            </button>
          </form>

          <aside className="panel analysis-history">
            <p className="kicker">Saved evidence</p>
            <h2>Analysis history</h2>
            <p className="muted small-copy">
              Saved runs freeze media, score revisions, model identities, boundaries,
              weights, and result distributions.
            </p>
            <div className="analysis-run-list">
              {runs.data?.map((run) => (
                <Link to={`/analysis/${run.id}`} key={run.id}>
                  <strong>{run.title}</strong>
                  <span>{titleCase(run.report_type)}</span>
                  <small>
                    {run.media_count} media · {run.group_count} groups ·{" "}
                    {formatDate(run.created_at)}
                  </small>
                </Link>
              ))}
              {runs.data?.length === 0 ? (
                <p className="empty-copy">No saved runs yet.</p>
              ) : null}
            </div>
          </aside>
        </section>
      ) : (
        <section className="saved-run-banner">
          <span>Immutable snapshot</span>
          <p>
            {savedRun.data.media_count} eligible · {savedRun.data.excluded_count} excluded
            · {savedRun.data.group_count} groups · {formatDate(savedRun.data.created_at)}
          </p>
          {savedRun.data.parent_run_id ? (
            <Link to={`/analysis/${savedRun.data.parent_run_id}`}>View parent run</Link>
          ) : null}
        </section>
      )}

      {report ? (
        <section className="analysis-results">
          <div className="analysis-result-toolbar">
            <div>
              <p className="kicker">{isSaved ? "Saved result" : "Live preview"}</p>
              <h2>{titleCase(report.report_type)}</h2>
            </div>
            <label>
              Show measure
              <select
                value={criterionKey}
                onChange={(event) => setCriterionKey(event.target.value)}
              >
                {criteria.map((criterion) => (
                  <option value={criterion.key} key={criterion.key}>
                    {criterion.label}
                  </option>
                ))}
              </select>
            </label>
            {!isSaved ? (
              <div className="save-analysis-controls">
                <input
                  aria-label="Saved analysis title"
                  placeholder="Name this analysis"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
                <button
                  className="secondary-button"
                  type="button"
                  disabled={saveMutation.isPending}
                  onClick={() => saveMutation.mutate()}
                >
                  {saveMutation.isPending ? "Freezing snapshot…" : "Save immutable run"}
                </button>
              </div>
            ) : null}
          </div>

          <div className="analysis-metric-strip">
            <Metric label="Eligible media" value={report.media_count} />
            <Metric label="Excluded" value={report.excluded_count} />
            <Metric label="Groups" value={report.group_count} />
            <Metric label="Effective criteria" value={report.effective_criteria.length} />
          </div>
          {report.warnings.length ? (
            <div className="analysis-warnings">
              {report.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}

          <ReferencePicker
            results={visibleResults}
            value={spec.reference_group_key}
            disabled={isSaved}
            onChange={(value) =>
              setSpec((current) => ({ ...current, reference_group_key: value }))
            }
          />

          {report.report_type === "lora_training_series" ? (
            <TrainingTrend results={visibleResults} />
          ) : null}
          {report.report_type === "checkpoint_lora_matrix" ? (
            <CheckpointLoraMatrix
              results={visibleResults}
              onOpen={isSaved ? setDrillGroup : undefined}
            />
          ) : (
            <ResultTable
              results={visibleResults}
              onOpen={isSaved ? setDrillGroup : undefined}
            />
          )}
          <StatisticsGuide />
        </section>
      ) : null}

      {runId && drillGroup ? (
        <MediaDrilldown
          media={media.data ?? []}
          loading={media.isPending}
          onClose={() => setDrillGroup(null)}
        />
      ) : null}
    </main>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ id: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option value={option.id} key={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function ReferencePicker({
  results,
  value,
  disabled,
  onChange,
}: {
  results: AnalysisResult[];
  value: string | null;
  disabled: boolean;
  onChange: (value: string | null) => void;
}) {
  return (
    <div className="reference-picker">
      <div>
        <strong>Reference group</strong>
        <small>
          Differences and Cliff&apos;s delta use this group as context. A reference
          does not turn the report into a winner declaration.
        </small>
      </div>
      <select
        value={value ?? ""}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value || null)}
      >
        <option value="">No reference</option>
        {results.map((result) => (
          <option value={result.group_key} key={result.group_key}>
            {result.group_label}
          </option>
        ))}
      </select>
      {!disabled && value ? (
        <small>Preview again to apply this reference.</small>
      ) : null}
    </div>
  );
}

function ResultTable({
  results,
  onOpen,
}: {
  results: AnalysisResult[];
  onOpen?: (groupKey: string) => void;
}) {
  return (
    <div className="analysis-table-wrap">
      <table className="analysis-table">
        <thead>
          <tr>
            <th>Group</th>
            <th>Distribution</th>
            <th>Mean / median</th>
            <th>95% mean interval</th>
            <th>Coverage</th>
            <th>Evidence</th>
            <th>vs reference</th>
          </tr>
        </thead>
        <tbody>
          {results.map((result) => (
            <tr key={result.group_key}>
              <td>
                {onOpen ? (
                  <button
                    className="analysis-group-link"
                    type="button"
                    onClick={() => onOpen(result.group_key)}
                  >
                    {result.group_label}
                  </button>
                ) : (
                  <strong>{result.group_label}</strong>
                )}
                <small>{boundaryText(result)}</small>
              </td>
              <td>
                <Histogram values={result.histogram} />
              </td>
              <td>
                <strong>{formatScore(result.mean)}</strong>
                <small>median {formatScore(result.median)}</small>
              </td>
              <td>{formatInterval(result.ci_low, result.ci_high)}</td>
              <td>
                {result.scored_count}/{result.eligible_count} (
                {Math.round(result.coverage * 100)}%)
                <small>
                  {result.na_count} N/A · {result.not_collected_count} missing
                </small>
              </td>
              <td>
                <span className={`evidence-chip ${result.evidence_strength}`}>
                  {evidenceLabel(result.evidence_strength)}
                </span>
              </td>
              <td>
                <strong>
                  {result.difference_from_reference === null
                    ? "—"
                    : `${result.difference_from_reference >= 0 ? "+" : ""}${result.difference_from_reference.toFixed(2)}`}
                </strong>
                <small>{explainEffect(result.effect_size)}</small>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {results.length === 0 ? (
        <p className="empty-copy">
          No groups were found. Check that completed evaluations have resolved workflow
          checkpoint/LoRA observations for this report.
        </p>
      ) : null}
    </div>
  );
}

function Histogram({ values }: { values: number[] }) {
  const maximum = Math.max(1, ...values);
  return (
    <div className="mini-histogram" aria-label={`Score counts 0 through 10: ${values.join(", ")}`}>
      {values.map((value, index) => (
        <i
          key={index}
          style={{ height: `${Math.max(4, (value / maximum) * 100)}%` }}
          title={`${index}: ${value}`}
        />
      ))}
    </div>
  );
}

function TrainingTrend({ results }: { results: AnalysisResult[] }) {
  const points = results.filter(
    (result) =>
      typeof result.dimensions.training_step === "number" && result.mean !== null,
  );
  if (!points.length) return null;
  const steps = points.map((result) => Number(result.dimensions.training_step));
  const minimum = Math.min(...steps);
  const maximum = Math.max(...steps);
  const x = (step: number) =>
    maximum === minimum ? 50 : 5 + ((step - minimum) / (maximum - minimum)) * 90;
  return (
    <section className="panel trend-panel">
      <div className="section-heading">
        <div>
          <p className="kicker">Non-linear view</p>
          <h3>Training-step trend</h3>
        </div>
        <span>Later is not assumed better</span>
      </div>
      <svg viewBox="0 0 100 46" role="img" aria-label="Mean score by LoRA training step">
        {[0, 5, 10].map((score) => (
          <line
            x1="5"
            x2="95"
            y1={42 - score * 3.7}
            y2={42 - score * 3.7}
            key={score}
          />
        ))}
        <polyline
          points={points
            .map(
              (result) =>
                `${x(Number(result.dimensions.training_step))},${42 - (result.mean ?? 0) * 3.7}`,
            )
            .join(" ")}
        />
        {points.map((result) => (
          <circle
            key={result.group_key}
            cx={x(Number(result.dimensions.training_step))}
            cy={42 - (result.mean ?? 0) * 3.7}
            r="1.4"
          >
            <title>
              Step {String(result.dimensions.training_step)}: mean{" "}
              {formatScore(result.mean)}, n={result.scored_count}
            </title>
          </circle>
        ))}
      </svg>
      <div className="trend-labels">
        {points.map((result) => (
          <span key={result.group_key}>
            <strong>{String(result.dimensions.training_step)}</strong>
            {formatScore(result.mean)} · n={result.scored_count}
          </span>
        ))}
      </div>
    </section>
  );
}

function CheckpointLoraMatrix({
  results,
  onOpen,
}: {
  results: AnalysisResult[];
  onOpen?: (groupKey: string) => void;
}) {
  const checkpoints = Array.from(
    new Set(results.map((result) => String(result.dimensions.checkpoint_label ?? "Checkpoint"))),
  );
  const loras = Array.from(
    new Set(results.map((result) => String(result.dimensions.lora_label ?? "LoRA"))),
  );
  const cell = new Map(
    results.map((result) => [
      `${String(result.dimensions.checkpoint_label)}::${String(result.dimensions.lora_label)}`,
      result,
    ]),
  );
  return (
    <div className="matrix-wrap">
      <table className="analysis-matrix">
        <thead>
          <tr>
            <th>Checkpoint ↓ / LoRA →</th>
            {loras.map((lora) => (
              <th key={lora}>{lora}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {checkpoints.map((checkpoint) => (
            <tr key={checkpoint}>
              <th>{checkpoint}</th>
              {loras.map((lora) => {
                const result = cell.get(`${checkpoint}::${lora}`);
                return (
                  <td key={lora}>
                    {result ? (
                      <button
                        type="button"
                        disabled={!onOpen}
                        onClick={() => onOpen?.(result.group_key)}
                        style={{
                          background: `color-mix(in srgb, var(--accent) ${(result.mean ?? 0) * 7}%, var(--surface-raised))`,
                        }}
                      >
                        <strong>{formatScore(result.mean)}</strong>
                        <small>
                          n={result.scored_count} · {evidenceLabel(result.evidence_strength)}
                        </small>
                      </button>
                    ) : (
                      <span>Insufficient</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatisticsGuide() {
  return (
    <details className="panel statistics-guide">
      <summary>How to read these numbers</summary>
      <div>
        <p>
          <strong>Mean</strong> is the arithmetic average. <strong>Median</strong> is
          the middle score and is less sensitive to a few unusually high or low ratings.
        </p>
        <p>
          <strong>95% bootstrap interval</strong> shows how uncertain the group mean is
          at this sample size. Wide or overlapping intervals are a reason for caution.
        </p>
        <p>
          <strong>Cliff&apos;s delta</strong> asks how often a random item from this group
          scores above rather than below a random item from the reference. It ranges
          from −1 to +1 and makes no normal-distribution assumption.
        </p>
        <p>
          <strong>Evidence labels</strong> summarize sample count, coverage, and interval
          width. They describe confidence in the observed tendency—not whether a model is
          good.
        </p>
      </div>
    </details>
  );
}

function WeightProfileForm({
  criteria,
  onCreated,
}: {
  criteria: AnalysisOptions["criteria"];
  onCreated: (profile: WeightingProfile) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [weights, setWeights] = useState<Record<string, number>>({});
  const create = useMutation({
    mutationFn: () =>
      apiRequest<WeightingProfile>("/api/v1/weighting-profiles", {
        method: "POST",
        body: JSON.stringify({
          name,
          weights,
          default_weight: 1,
        }),
      }),
    onSuccess: onCreated,
  });
  const uniqueCriteria = Array.from(
    new Map(criteria.map((criterion) => [criterion.id, criterion])).values(),
  );
  return (
    <div className="weight-profile-form">
      <label>
        Profile name
        <input
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <div className="weight-grid">
        {uniqueCriteria.map((criterion) => (
          <label key={criterion.id}>
            {criterion.label}
            <input
              type="number"
              min="0"
              max="100"
              step="0.25"
              value={weights[criterion.id] ?? 1}
              onChange={(event) =>
                setWeights((current) => ({
                  ...current,
                  [criterion.id]: Number(event.target.value),
                }))
              }
            />
          </label>
        ))}
      </div>
      {create.error ? <p className="notice error-notice">{create.error.message}</p> : null}
      <button
        className="secondary-button"
        type="button"
        disabled={create.isPending || !name.trim()}
        onClick={() => create.mutate()}
      >
        Save profile version
      </button>
    </div>
  );
}

function MediaDrilldown({
  media,
  loading,
  onClose,
}: {
  media: AnalysisMedia[];
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <aside className="analysis-drilldown" aria-label="Media behind result">
      <div className="section-heading">
        <div>
          <p className="kicker">Frozen membership</p>
          <h2>Media behind this group</h2>
        </div>
        <button className="text-button inline-text-button" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      {loading ? <p>Loading media…</p> : null}
      <div className="analysis-media-grid">
        {media.map((item) => (
          <Link to={`/library/${item.media_id}`} key={item.media_id}>
            <img src={item.preview_url} alt="" loading="lazy" />
            <span>{formatScore(item.composite_score)}</span>
          </Link>
        ))}
      </div>
    </aside>
  );
}

function boundaryText(result: AnalysisResult): string {
  const values = [
    result.dimensions.architecture_family,
    result.dimensions.pipeline_pattern,
    result.dimensions.slot ?? result.dimensions.checkpoint_slot,
  ].filter((value): value is string => typeof value === "string" && value.length > 0);
  return values.map(titleCase).join(" · ");
}
