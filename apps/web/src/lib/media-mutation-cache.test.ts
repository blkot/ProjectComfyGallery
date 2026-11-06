import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";

import { refreshMediaMutationCaches } from "./media-mutation-cache";

describe("media mutation registry cache", () => {
  it("patches cached usage and lookup media while preserving entry and page metadata", async () => {
    const client = new QueryClient();
    const lookupKey = ["prompt-registry-lookup", "source-12"];
    const usageKey = ["prompt-registry-usage", "source-12", "character", 48];
    const lookup = {
      entry: { positive_prompt: "A calm landscape" },
      media: [{ id: "one", favorite: false, content_rating: "sfw", is_trash: false }, { id: "two", favorite: false }],
      total_media: 100,
      limit: 48,
      offset: 48,
    };
    client.setQueryData(lookupKey, lookup);
    client.setQueryData(usageKey, lookup);
    client.setQueryData(["prompt-registry-usage-navigation", "one", "scope"], { next_id: "two" });

    await refreshMediaMutationCaches(client, "one", { favorite: true, content_rating: "nsfw", is_trash: true });

    for (const key of [lookupKey, usageKey]) {
      expect(client.getQueryData(key)).toEqual({
        ...lookup,
        media: [{ ...lookup.media[0], favorite: true, content_rating: "nsfw", is_trash: true }, lookup.media[1]],
      });
      expect(client.getQueryState(key)?.isInvalidated).toBe(true);
    }
    expect(client.getQueryState(["prompt-registry-usage-navigation", "one", "scope"])?.isInvalidated).toBe(true);
    client.clear();
  });

  it("marks an active heatmap stale without refetching until its owner requests it", async () => {
    const client = new QueryClient();
    const queryKey = ["prompt-registry-heatmap", "source"];
    const queryFn = vi.fn().mockResolvedValue({ items: [], total: 0 });
    await client.fetchQuery({ queryKey, queryFn, staleTime: Infinity });
    const observer = new QueryObserver(client, { queryKey, queryFn, staleTime: Infinity });
    const unsubscribe = observer.subscribe(() => undefined);

    await refreshMediaMutationCaches(client, "one", { favorite: true });

    expect(queryFn).toHaveBeenCalledTimes(1);
    expect(client.getQueryState(queryKey)?.isInvalidated).toBe(true);
    expect(client.getQueryData(queryKey)).toEqual({ items: [], total: 0 });
    unsubscribe();
    client.clear();
  });
});
