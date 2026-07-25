import { describe, expect, it } from "vitest";

import { type Evaluation } from "./api";
import { sameScoreChoice, scoreChoice } from "./evaluation";

function evaluationWithScore(
  state: "scored" | "na",
  value: number | null,
): Evaluation {
  return {
    id: "evaluation",
    media_id: "media",
    template_id: "template",
    template_name: "Image core V1",
    template_version: 1,
    module: "core",
    evaluation_kind: "base",
    progress_state: "in_progress",
    is_trash: false,
    version: 2,
    completed_at: null,
    created_at: "2026-07-26T00:00:00Z",
    updated_at: "2026-07-26T00:00:00Z",
    criteria: [],
    scores: [
      {
        criterion_version_id: "criterion",
        state,
        value,
        na_reason: state === "na" ? "Not visible" : null,
        updated_at: "2026-07-26T00:00:00Z",
      },
    ],
  };
}

describe("shared evaluation controls", () => {
  it("distinguishes scored zero, N/A, and unset choices", () => {
    expect(scoreChoice(evaluationWithScore("scored", 0), "criterion")).toEqual({
      state: "scored",
      value: 0,
      na_reason: null,
    });
    expect(scoreChoice(evaluationWithScore("na", null), "criterion")).toEqual({
      state: "na",
      value: null,
      na_reason: "Not visible",
    });
    expect(scoreChoice(evaluationWithScore("scored", 4), "missing")).toEqual({
      state: "unset",
      value: null,
      na_reason: null,
    });
  });

  it("compares complete score choices before autosaving", () => {
    expect(
      sameScoreChoice(
        { state: "scored", value: 7, na_reason: null },
        { state: "scored", value: 7, na_reason: null },
      ),
    ).toBe(true);
    expect(
      sameScoreChoice(
        { state: "na", value: null, na_reason: "Hidden" },
        { state: "na", value: null, na_reason: null },
      ),
    ).toBe(false);
  });
});
