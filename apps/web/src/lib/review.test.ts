import { describe, expect, it } from "vitest";

import { resolveReviewPosition } from "./review";

describe("review position", () => {
  it("resumes at the persisted cursor when the URL has no explicit position", () => {
    expect(resolveReviewPosition(null, 37)).toBe(37);
  });

  it("honors an explicit non-negative URL position", () => {
    expect(resolveReviewPosition("4", 37)).toBe(4);
  });

  it("falls back to the persisted cursor for an invalid URL position", () => {
    expect(resolveReviewPosition("-1", 8)).toBe(8);
    expect(resolveReviewPosition("not-a-number", 8)).toBe(8);
  });
});
