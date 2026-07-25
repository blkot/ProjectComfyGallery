import { useState } from "react";

import {
  type Evaluation,
  type EvaluationCriterion,
  type EvaluationScore,
} from "../lib/api";
import { type ScoreChoice } from "../lib/evaluation";
import { titleCase } from "../lib/format";

export function EvaluationSection({
  evaluation,
  disabled,
  commit,
}: {
  evaluation: Evaluation;
  disabled: boolean;
  commit: (
    evaluation: Evaluation,
    criterionId: string,
    next: ScoreChoice,
  ) => void;
}) {
  return (
    <section className="evaluation-module">
      <div className="evaluation-module-heading">
        <span>
          <p className="kicker">{titleCase(evaluation.evaluation_kind)}</p>
          <h2>{evaluation.template_name}</h2>
        </span>
        <span className="evaluation-state" data-state={evaluation.progress_state}>
          {titleCase(evaluation.progress_state)}
        </span>
      </div>
      {evaluation.criteria.map((criterion) => {
        const score = evaluation.scores.find(
          (candidate) =>
            candidate.criterion_version_id === criterion.criterion_version_id,
        );
        return (
          <CriterionControl
            criterion={criterion}
            score={score}
            disabled={disabled}
            onCommit={(next) =>
              commit(evaluation, criterion.criterion_version_id, next)
            }
            key={`${criterion.criterion_version_id}-${score?.updated_at ?? "unset"}`}
          />
        );
      })}
    </section>
  );
}

function CriterionControl({
  criterion,
  score,
  disabled,
  onCommit,
}: {
  criterion: EvaluationCriterion;
  score: EvaluationScore | undefined;
  disabled: boolean;
  onCommit: (next: ScoreChoice) => void;
}) {
  const committed = score?.state === "scored" ? score.value : null;
  const [draft, setDraft] = useState<number | null>(committed);
  const isNa = score?.state === "na";

  function commitDraft() {
    if (draft === null || disabled) return;
    onCommit({ state: "scored", value: draft, na_reason: null });
  }

  return (
    <article
      className="criterion-control"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Delete" || event.key === "Backspace") {
          event.preventDefault();
          onCommit({ state: "unset", value: null, na_reason: null });
        }
      }}
    >
      <div className="criterion-heading">
        <span>
          <strong>{criterion.label}</strong>
          <small>{criterion.guidance}</small>
        </span>
        <output aria-label={`${criterion.label} value`}>
          {isNa ? "N/A" : (draft ?? "—")}
        </output>
      </div>
      <input
        className="criterion-slider"
        data-unset={draft === null || isNa}
        aria-label={criterion.label}
        aria-valuetext={
          isNa ? "Not applicable" : draft === null ? "Not set" : String(draft)
        }
        type="range"
        min="0"
        max="10"
        step="1"
        value={draft ?? 5}
        disabled={disabled}
        onChange={(event) => setDraft(Number(event.target.value))}
        onPointerUp={commitDraft}
        onBlur={commitDraft}
        onKeyUp={(event) => {
          if (
            ["ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"].includes(
              event.key,
            )
          ) {
            commitDraft();
          }
        }}
      />
      <div className="criterion-scale" aria-hidden="true">
        <span>0</span>
        <span>5</span>
        <span>10</span>
      </div>
      <details className="criterion-anchors">
        <summary>0 / 5 / 10 anchors</summary>
        <dl>
          <div>
            <dt>0</dt>
            <dd>{criterion.anchor_0}</dd>
          </div>
          <div>
            <dt>5</dt>
            <dd>{criterion.anchor_5}</dd>
          </div>
          <div>
            <dt>10</dt>
            <dd>{criterion.anchor_10}</dd>
          </div>
        </dl>
      </details>
      <div className="criterion-actions">
        <button
          className="text-button"
          type="button"
          disabled={disabled || (!score && draft === null)}
          onClick={() => {
            setDraft(null);
            onCommit({ state: "unset", value: null, na_reason: null });
          }}
        >
          Clear
        </button>
        <button
          className="text-button"
          data-active={isNa}
          type="button"
          disabled={disabled}
          onClick={() =>
            onCommit(
              isNa
                ? { state: "unset", value: null, na_reason: null }
                : { state: "na", value: null, na_reason: null },
            )
          }
        >
          {isNa ? "Unset N/A" : "N/A"}
        </button>
      </div>
    </article>
  );
}
