import type { AnalysisResult } from "./api";

export function formatScore(value: number | null): string {
  return value === null ? "—" : value.toFixed(2);
}

export function formatInterval(low: number | null, high: number | null): string {
  return low === null || high === null ? "Not enough data" : `${low.toFixed(2)}–${high.toFixed(2)}`;
}

export function explainEffect(value: number | null): string {
  if (value === null) return "Choose a reference group to calculate this tendency.";
  const magnitude = Math.abs(value);
  const strength =
    magnitude < 0.147
      ? "negligible"
      : magnitude < 0.33
        ? "small"
        : magnitude < 0.474
          ? "medium"
          : "large";
  const direction =
    value === 0 ? "neither direction" : value > 0 ? "this group" : "the reference";
  return `${strength[0].toUpperCase()}${strength.slice(1)} tendency toward ${direction}.`;
}

export function criterionResults(
  results: AnalysisResult[],
  criterionKey: string,
): AnalysisResult[] {
  return results
    .filter((result) => result.criterion_key === criterionKey)
    .sort((left, right) => {
      const leftStep = Number(left.dimensions.training_step);
      const rightStep = Number(right.dimensions.training_step);
      if (Number.isFinite(leftStep) && Number.isFinite(rightStep)) {
        return leftStep - rightStep;
      }
      return left.group_label.localeCompare(right.group_label);
    });
}

export function evidenceLabel(value: AnalysisResult["evidence_strength"]): string {
  if (value === "stronger") return "Stronger evidence";
  if (value === "suggestive") return "Suggestive";
  return "Insufficient";
}
