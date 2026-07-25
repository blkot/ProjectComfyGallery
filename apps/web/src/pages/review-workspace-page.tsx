import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import {
  EvaluationSection,
} from "../components/evaluation-controls";
import {
  apiRequest,
  type Evaluation,
  type ReviewItem,
  type ReviewSession,
} from "../lib/api";
import {
  sameScoreChoice,
  scoreChoice,
  type ScoreChoice,
} from "../lib/evaluation";
import { titleCase } from "../lib/format";
import { resolveReviewPosition } from "../lib/review";

type UndoEntry = {
  evaluationId: string;
  criterionId: string;
  previous: ScoreChoice;
};

export function ReviewWorkspacePage() {
  const { sessionId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const [undoEntry, setUndoEntry] = useState<UndoEntry | null>(null);

  const session = useQuery({
    queryKey: ["review-session", sessionId],
    queryFn: () =>
      apiRequest<ReviewSession>(`/api/v1/review-sessions/${sessionId}`),
    enabled: Boolean(sessionId),
  });
  const position = resolveReviewPosition(
    searchParams.get("position"),
    session.data?.current_cursor,
  );
  const itemKey = ["review-item", sessionId, position] as const;
  const item = useQuery({
    queryKey: itemKey,
    queryFn: () =>
      apiRequest<ReviewItem>(
        `/api/v1/review-sessions/${sessionId}/items/${position}`,
      ),
    enabled: Boolean(sessionId && session.data),
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
      _replaceEvaluation(queryClient, itemKey, updated);
      if (variables.recordUndo) {
        setUndoEntry({
          evaluationId: variables.evaluation.id,
          criterionId: variables.criterionId,
          previous: variables.previous,
        });
      } else {
        setUndoEntry(null);
      }
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["review-sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
      ]);
    },
  });
  const trash = useMutation({
    mutationFn: ({
      evaluation,
      restore,
    }: {
      evaluation: Evaluation;
      restore: boolean;
    }) =>
      apiRequest<Evaluation>(
        `/api/v1/evaluations/${evaluation.id}/${restore ? "restore" : "trash"}`,
        {
          method: "POST",
          body: JSON.stringify({ expected_version: evaluation.version }),
        },
      ),
    onSuccess: (updated) => {
      _replaceEvaluation(queryClient, itemKey, updated);
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
      ]);
    },
  });
  const move = useMutation({
    mutationFn: (nextPosition: number) =>
      apiRequest<ReviewSession>(`/api/v1/review-sessions/${sessionId}`, {
        method: "PATCH",
        body: JSON.stringify({ current_cursor: nextPosition }),
      }),
    onSuccess: (updated, nextPosition) => {
      queryClient.setQueryData(["review-session", sessionId], updated);
      setSearchParams({ position: String(nextPosition) });
    },
  });

  useEffect(() => {
    if (!item.data || position + 1 >= item.data.session.candidate_count) return;
    void queryClient.prefetchQuery({
      queryKey: ["review-item", sessionId, position + 1],
      queryFn: () =>
        apiRequest<ReviewItem>(
          `/api/v1/review-sessions/${sessionId}/items/${position + 1}`,
        ),
    });
  }, [item.data, position, queryClient, sessionId]);

  function navigateTo(nextPosition: number) {
    if (
      move.isPending ||
      !item.data ||
      nextPosition < 0 ||
      nextPosition >= item.data.session.candidate_count
    ) {
      return;
    }
    move.mutate(nextPosition);
  }

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      if (!event.altKey) return;
      if (event.key === "ArrowLeft") navigateTo(position - 1);
      if (event.key === "ArrowRight") navigateTo(position + 1);
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  });

  const baseEvaluation = item.data?.evaluations.find(
    (evaluation) => evaluation.evaluation_kind === "base",
  );
  const saving = saveScore.isPending || trash.isPending || move.isPending;

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
    if (!undoEntry || !item.data) return;
    const evaluation = item.data.evaluations.find(
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

  if (session.isError || item.isError) {
    return (
      <main className="page">
        <p className="notice error-notice" role="alert">
          {session.error?.message || item.error?.message || "The review could not open."}
        </p>
      </main>
    );
  }
  if (!item.data) {
    return (
      <main className="route-pending" aria-live="polite">
        <span className="spinner" />
        <span>Preparing blind review…</span>
      </main>
    );
  }

  return (
    <main className="review-workspace">
      <div className="review-columns">
        <section className="review-preview-pane" aria-label="Media preview">
          <div className="review-media-frame">
            {item.data.media.kind === "video" ? (
              <video
                src={item.data.media.playback_url}
                controls
                playsInline
                preload="metadata"
              />
            ) : (
              <img src={item.data.media.preview_url} alt="Media under review" />
            )}
            {baseEvaluation?.is_trash ? (
              <span className="review-trash-overlay">Marked Trash</span>
            ) : null}
          </div>
        </section>

        <aside className="review-criteria-pane">
          <header className="review-topbar">
            <Link className="review-exit-link" to="/review">
              ← Exit
            </Link>
            <span>
              <strong>
                {position + 1} / {item.data.session.candidate_count}
              </strong>
              <small>
                {item.data.session.progress_counts.complete ?? 0} complete ·{" "}
                {item.data.session.progress_counts.in_progress ?? 0} in progress
              </small>
            </span>
            <span
              className="review-save-state"
              data-state={saving ? "wait" : "ok"}
            >
              {saving ? "Saving…" : "All changes saved"}
            </span>
          </header>

          <div className="review-criteria-scroll">
            <section className="review-prompts">
              <div className="section-heading">
                <div>
                  <p className="kicker">Exact embedded text</p>
                  <h2>Prompt</h2>
                </div>
                <span className="blind-badge">Config hidden</span>
              </div>
              {item.data.prompts.map((prompt, index) => (
                <details key={`${prompt.label}-${index}`} open={index === 0}>
                  <summary>{titleCase(prompt.label)}</summary>
                  <p>{prompt.text}</p>
                </details>
              ))}
              {item.data.prompts.length === 0 ? (
                <p className="muted">No prompt was extracted for this media.</p>
              ) : null}
            </section>

            {item.data.evaluations.map((evaluation) => (
              <EvaluationSection
                evaluation={evaluation}
                disabled={saving}
                commit={commitScore}
                key={evaluation.id}
              />
            ))}

            {saveScore.error || trash.error || move.error ? (
              <p className="notice error-notice" role="alert">
                {saveScore.error?.message ||
                  trash.error?.message ||
                  move.error?.message}
              </p>
            ) : null}

            <section className="review-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={!undoEntry || saving}
                onClick={undo}
              >
                Undo last score
              </button>
              {baseEvaluation ? (
                <button
                  className={
                    baseEvaluation.is_trash ? "secondary-button" : "danger-button"
                  }
                  type="button"
                  disabled={saving}
                  onClick={() =>
                    trash.mutate({
                      evaluation: baseEvaluation,
                      restore: baseEvaluation.is_trash,
                    })
                  }
                >
                  {baseEvaluation.is_trash
                    ? "Restore from Trash"
                    : "Mark as Trash"}
                </button>
              ) : null}
            </section>

            <nav className="review-navigation" aria-label="Review navigation">
              <button
                className="secondary-button"
                type="button"
                disabled={saving || position === 0}
                onClick={() => navigateTo(position - 1)}
              >
                Previous
              </button>
              <span>Alt + ← / →</span>
              <button
                className="primary-button"
                type="button"
                disabled={
                  saving || position + 1 >= item.data.session.candidate_count
                }
                onClick={() => navigateTo(position + 1)}
              >
                Next
              </button>
            </nav>
          </div>
        </aside>
      </div>
    </main>
  );
}

function _replaceEvaluation(
  queryClient: ReturnType<typeof useQueryClient>,
  key: readonly unknown[],
  updated: Evaluation,
) {
  queryClient.setQueryData<ReviewItem>(key, (current) =>
    current
      ? {
          ...current,
          evaluations: current.evaluations.map((evaluation) =>
            evaluation.id === updated.id ? updated : evaluation,
          ),
        }
      : current,
  );
}
