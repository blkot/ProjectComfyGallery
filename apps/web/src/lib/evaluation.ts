import { type Evaluation } from "./api";

export type ScoreChoice =
  | { state: "scored"; value: number; na_reason: null }
  | { state: "na"; value: null; na_reason: string | null }
  | { state: "unset"; value: null; na_reason: null };

export function scoreChoice(
  evaluation: Evaluation,
  criterionId: string,
): ScoreChoice {
  const score = evaluation.scores.find(
    (candidate) => candidate.criterion_version_id === criterionId,
  );
  if (!score) return { state: "unset", value: null, na_reason: null };
  if (score.state === "na") {
    return { state: "na", value: null, na_reason: score.na_reason };
  }
  return { state: "scored", value: score.value ?? 0, na_reason: null };
}

export function sameScoreChoice(left: ScoreChoice, right: ScoreChoice): boolean {
  return (
    left.state === right.state &&
    left.value === right.value &&
    left.na_reason === right.na_reason
  );
}
