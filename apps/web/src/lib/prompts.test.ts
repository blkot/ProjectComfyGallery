import { describe, expect, it } from "vitest";

import { orderPrompts, promptRoleRank } from "./prompts";

describe("prompt ordering", () => {
  it("puts positive or main prompts first and negative prompts last", () => {
    const prompts = [
      { id: "negative", role: "negative" },
      { id: "unknown", role: null },
      { id: "positive", role: "positive" },
    ];

    expect(orderPrompts(prompts).map((prompt) => prompt.id)).toEqual([
      "positive",
      "unknown",
      "negative",
    ]);
    expect(prompts.map((prompt) => prompt.id)).toEqual([
      "negative",
      "unknown",
      "positive",
    ]);
  });

  it("accepts friendly aliases for a primary prompt", () => {
    expect(promptRoleRank("main")).toBe(0);
    expect(promptRoleRank("positive-prompt")).toBe(0);
    expect(promptRoleRank("negative_prompt")).toBe(2);
  });
});
