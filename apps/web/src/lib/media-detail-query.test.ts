import { afterEach, describe, expect, it, vi } from "vitest";
import type { MediaDetail } from "./api";
import { clearMediaAssetPreloads, preloadMediaAsset } from "./media-detail-query";

afterEach(() => { clearMediaAssetPreloads(); vi.restoreAllMocks(); });

function item(id: string): MediaDetail {
  return { id, kind: "image", original_url: `/test-warm/${id}`, width: 2048, height: 3072 } as MediaDetail;
}

describe("neighbor image warming", () => {
  it("does not cancel a warming original when its neighbor effect is cleaned up", () => {
    const remove = vi.spyOn(HTMLImageElement.prototype, "removeAttribute");
    preloadMediaAsset(item("promoted-current"))();
    expect(remove).not.toHaveBeenCalledWith("src");
  });

  it("deduplicates the same original across repeated four-media traversal", () => {
    const sources = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    for (const id of ["one", "two", "three", "four", "three", "two", "one"]) preloadMediaAsset(item(id));
    expect(sources.mock.calls.filter(([src]) => src === "/test-warm/one")).toHaveLength(1);
    expect(sources.mock.calls.filter(([src]) => src === "/test-warm/two")).toHaveLength(1);
  });

  it("bounds originals to four entries and evicts the least recently used", () => {
    const sources = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    for (const id of ["one", "two", "three", "four", "five", "two", "one"]) preloadMediaAsset(item(id));
    expect(sources.mock.calls.filter(([src]) => src === "/test-warm/one")).toHaveLength(2);
    expect(sources.mock.calls.filter(([src]) => src === "/test-warm/two")).toHaveLength(1);
  });

  it("skips speculative images that exceed the decoded memory budget", () => {
    const sources = vi.spyOn(HTMLImageElement.prototype, "src", "set");
    preloadMediaAsset({ ...item("oversized"), width: 12000, height: 12000 });
    expect(sources).not.toHaveBeenCalled();
  });
});
