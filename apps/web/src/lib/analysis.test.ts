import { describe, expect, it } from "vitest";

import { evidenceLabel, explainEffect, formatInterval, formatScore } from "./analysis";

describe("analysis presentation", () => {
  it("keeps missing statistics visibly missing", () => {
    expect(formatScore(null)).toBe("—");
    expect(formatInterval(null, 5)).toBe("Not enough data");
  });

  it("explains Cliff's delta as a tendency, not a winner", () => {
    expect(explainEffect(0.6)).toBe("Large tendency toward this group.");
    expect(explainEffect(-0.2)).toBe("Small tendency toward the reference.");
    expect(explainEffect(null)).toContain("Choose a reference");
  });

  it("expands evidence labels in plain language", () => {
    expect(evidenceLabel("stronger")).toBe("Stronger evidence");
    expect(formatScore(7.126)).toBe("7.13");
  });
});
