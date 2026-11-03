import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { readPersistedState, usePersistedState } from "./use-persisted-state";

const isBoolean = (value: unknown): value is boolean => typeof value === "boolean";

beforeEach(() => {
  window.localStorage.clear();
});

describe("readPersistedState", () => {
  it("returns the fallback when the key is absent", () => {
    expect(readPersistedState("preference", false, isBoolean)).toBe(false);
  });

  it("returns a stored value that passes validation", () => {
    window.localStorage.setItem("preference", "true");
    expect(readPersistedState("preference", false, isBoolean)).toBe(true);
  });

  it("falls back for malformed JSON or a rejected value", () => {
    window.localStorage.setItem("broken", "{not-json");
    expect(readPersistedState("broken", false, isBoolean)).toBe(false);

    window.localStorage.setItem("wrong-type", JSON.stringify("yes"));
    expect(readPersistedState("wrong-type", false, isBoolean)).toBe(false);
  });

  it("does not throw when storage is unavailable", () => {
    const getItem = vi
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => {
        throw new Error("storage denied");
      });
    try {
      expect(readPersistedState("preference", false, isBoolean)).toBe(false);
    } finally {
      getItem.mockRestore();
    }
  });
});

describe("usePersistedState", () => {
  it("restores the stored value on mount", () => {
    window.localStorage.setItem("preference", "true");
    const { result } = renderHook(() =>
      usePersistedState("preference", false, isBoolean),
    );
    expect(result.current[0]).toBe(true);
  });

  it("writes changes back to storage", () => {
    const { result } = renderHook(() =>
      usePersistedState("preference", false, isBoolean),
    );
    act(() => result.current[1](true));
    expect(JSON.parse(window.localStorage.getItem("preference") ?? "null")).toBe(
      true,
    );
  });
});
