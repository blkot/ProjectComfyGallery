import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  EvaluationSection,
} from "./evaluation-controls";
import {
  apiRequest,
  type Evaluation,
  type MediaEvaluationContext,
} from "../lib/api";
import {
  sameScoreChoice,
  scoreChoice,
  type ScoreChoice,
} from "../lib/evaluation";
import { titleCase } from "../lib/format";

type UndoEntry = {
  evaluationId: string;
  criterionId: string;
  previous: ScoreChoice;
};

export function MediaEvaluationPanel({ mediaId }: { mediaId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["media-evaluation-context", mediaId] as const;
  const [undoEntry, setUndoEntry] = useState<UndoEntry | null>(null);
  const context = useQuery({
    queryKey,
    queryFn: () =>
      apiRequest<MediaEvaluationContext>(
        `/api/v1/media/${mediaId}/evaluation-context`,
        { method: "POST" },
      ),
    staleTime: 30_000,
  });
  const saveScore = useMutation({
    mutationFn: async ({
      evaluation,
      criterionId,
      next,
    }: {
      evaluation: Evaluation;
      criterionId: string;
      next: ScoreChoice;
      previous: ScoreChoice;
      recordUndo: boolean;
    }) => {
      if (next.state === "unset") {
        return apiRequest<Evaluation>(
          `/api/v1/evaluations/${evaluation.id}/scores/${criterionId}`,
          {
            method: "DELETE",
            body: JSON.stringify({ expected_version: evaluation.version }),
          },
        );
      }
      return apiRequest<Evaluation>(
        `/api/v1/evaluations/${evaluation.id}/scores/${criterionId}`,
        {
          method: "PUT",
          body: JSON.stringify({
            expected_version: evaluation.version,
            ...next,
          }),
        },
      );
    },
    onSuccess: (updated, variables) => {
      _replaceEvaluation(queryClient, queryKey, updated);
      if (variables.recordUndo) {
        setUndoEntry({
          evaluationId: variables.evaluation.id,
          criterionId: variables.criterionId,
          previous: variables.previous,
        });
      } else {
        setUndoEntry(null);
      }
      void _invalidateEvaluationViews(queryClient, mediaId);
    },
  });
  const toggleModule = useMutation({
    mutationFn: ({ module, enabled }: { module: string; enabled: boolean }) =>
      apiRequest<MediaEvaluationContext>(
        `/api/v1/media/${mediaId}/evaluation-modules/${encodeURIComponent(module)}`,
        {
          method: "PUT",
          body: JSON.stringify({ enabled }),
        },
      ),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      setUndoEntry(null);
      void _invalidateEvaluationViews(queryClient, mediaId);
    },
  });

  const data = context.data;
  const saving = saveScore.isPending || toggleModule.isPending;
  const baseEvaluation = data?.evaluations.find(
    (evaluation) => evaluation.evaluation_kind === "base",
  );
  const resolvedCount =
    data?.evaluations.reduce(
      (total, evaluation) => total + evaluation.scores.length,
      0,
    ) ?? 0;
  const criterionCount =
    data?.evaluations.reduce(
      (total, evaluation) => total + evaluation.criteria.length,
      0,
    ) ?? 0;

  function commitScore(
    evaluation: Evaluation,
    criterionId: string,
    next: ScoreChoice,
    recordUndo = true,
  ) {
    const previous = scoreChoice(evaluation, criterionId);
    if (sameScoreChoice(previous, next)) return;
    saveScore.mutate({
      evaluation,
      criterionId,
      next,
      previous,
      recordUndo,
    });
  }

  function undo() {
    if (!undoEntry || !data) return;
    const evaluation = data.evaluations.find(
      (candidate) => candidate.id === undoEntry.evaluationId,
    );
    if (!evaluation) return;
    commitScore(
      evaluation,
      undoEntry.criterionId,
      undoEntry.previous,
      false,
    );
  }

  if (context.isPending) {
    return (
      <div className="media-evaluation-loading" aria-live="polite">
        <span className="spinner" />
        <span>Preparing this media’s evaluation…</span>
      </div>
    );
  }
  if (context.isError || !data) {
    return (
      <p className="notice error-notice" role="alert">
        {context.error?.message || "This media’s evaluation could not be loaded."}
      </p>
    );
  }

  return (
    <section className="media-evaluation-panel">
      <header className="media-evaluation-summary">
        <span>
          <p className="kicker">Single-media evaluation</p>
          <strong>
            {resolvedCount} / {criterionCount} criteria resolved
          </strong>
        </span>
        <span className="media-evaluation-summary-state">
          <span
            className="evaluation-state"
            data-state={data.progress_state}
          >
            {titleCase(data.progress_state)}
          </span>
          <small
            className="review-save-state"
            data-state={saving ? "wait" : "ok"}
          >
            {saving ? "Saving…" : "All changes saved"}
          </small>
        </span>
      </header>

      <section className="media-evaluation-modules">
        <div className="section-heading">
          <div>
            <p className="kicker">Applicable criteria</p>
            <h2>Modules</h2>
          </div>
        </div>
        <div className="media-evaluation-module-list">
          <div className="media-evaluation-module-row">
            <span>
              <strong>Core</strong>
              <small>Required for every {baseEvaluation ? "media" : "record"}</small>
            </span>
            <span className="module-required-badge">Required</span>
          </div>
          {data.available_modules.map((module) => (
            <label className="media-evaluation-module-row" key={module.module}>
              <span>
                <strong>{module.label}</strong>
                <small>
                  {module.enabled
                    ? `${titleCase(module.progress_state ?? "not started")} supplemental evaluation`
                    : module.has_saved_scores
                      ? "Disabled · saved scores preserved"
                      : "Optional supplemental evaluation"}
                </small>
              </span>
              <input
                type="checkbox"
                role="switch"
                aria-label={`Enable ${module.label} module`}
                checked={module.enabled}
                disabled={saving}
                onChange={(event) =>
                  toggleModule.mutate({
                    module: module.module,
                    enabled: event.target.checked,
                  })
                }
              />
            </label>
          ))}
        </div>
      </section>

      <section className="media-evaluation-prompts">
        <div className="section-heading">
          <div>
            <p className="kicker">Exact embedded text</p>
            <h2>Prompt</h2>
          </div>
          <span className="document-count">{data.prompts.length}</span>
        </div>
        {data.prompts.map((prompt, index) => (
          <details
            data-role={prompt.role ?? "unclassified"}
            key={`${prompt.label}-${index}`}
            open={index === 0}
          >
            <summary>{titleCase(prompt.label)}</summary>
            <p>{prompt.text}</p>
          </details>
        ))}
        {data.prompts.length === 0 ? (
          <p className="muted">No prompt was extracted for this media.</p>
        ) : null}
      </section>

      {data.evaluations.map((evaluation) => (
        <EvaluationSection
          evaluation={evaluation}
          disabled={saving}
          commit={commitScore}
          key={evaluation.id}
        />
      ))}

      {saveScore.error || toggleModule.error ? (
        <p className="notice error-notice" role="alert">
          {saveScore.error?.message || toggleModule.error?.message}
        </p>
      ) : null}

      <section className="media-evaluation-actions">
        <button
          className="secondary-button"
          type="button"
          disabled={!undoEntry || saving}
          onClick={undo}
        >
          Undo last score
        </button>
      </section>
    </section>
  );
}

function _replaceEvaluation(
  queryClient: ReturnType<typeof useQueryClient>,
  key: readonly unknown[],
  updated: Evaluation,
) {
  queryClient.setQueryData<MediaEvaluationContext>(key, (current) => {
    if (!current) return current;
    const evaluations = current.evaluations.map((evaluation) =>
      evaluation.id === updated.id ? updated : evaluation,
    );
    return {
      ...current,
      evaluations,
      progress_state: _combinedProgress(evaluations),
      is_trash:
        updated.evaluation_kind === "base" ? updated.is_trash : current.is_trash,
      available_modules: current.available_modules.map((module) =>
        module.module === updated.module
          ? {
              ...module,
              progress_state: updated.progress_state,
              has_saved_scores: updated.scores.length > 0,
            }
          : module,
      ),
    };
  });
}

function _combinedProgress(
  evaluations: Evaluation[],
): MediaEvaluationContext["progress_state"] {
  if (evaluations.every((evaluation) => evaluation.progress_state === "complete")) {
    return "complete";
  }
  if (
    evaluations.every(
      (evaluation) => evaluation.progress_state === "not_started",
    )
  ) {
    return "not_started";
  }
  return "in_progress";
}

async function _invalidateEvaluationViews(
  queryClient: ReturnType<typeof useQueryClient>,
  mediaId: string,
) {
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["media"] }),
    queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
    queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
    queryClient.invalidateQueries({ queryKey: ["review-sessions"] }),
    queryClient.invalidateQueries({ queryKey: ["review-item"] }),
  ]);
}
