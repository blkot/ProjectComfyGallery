import type { QueryClient } from "@tanstack/react-query";

import type { PromptRegistryLookup, PromptRegistryMedia } from "./api";

type PromptMediaPatch = Partial<
  Pick<PromptRegistryMedia, "favorite" | "content_rating" | "is_trash">
>;

/** Keep the mounted registry in sync without clearing its entry or usage data. */
export async function refreshMediaMutationCaches(
  queryClient: QueryClient,
  mediaId: string,
  patch: PromptMediaPatch = {},
) {
  for (const queryKey of ["prompt-registry-lookup", "prompt-registry-usage"]) {
    queryClient.setQueriesData<PromptRegistryLookup>(
      { queryKey: [queryKey] },
      (current) =>
        current?.media
          ? {
              ...current,
              media: current.media.map((media) =>
                media.id === mediaId ? { ...media, ...patch } : media,
              ),
            }
          : current,
    );
  }

  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["prompt-registry-lookup"] }),
    queryClient.invalidateQueries({ queryKey: ["prompt-registry-usage"] }),
    queryClient.invalidateQueries({ queryKey: ["prompt-registry-usage-navigation"] }),
    queryClient.invalidateQueries({ queryKey: ["photo-wall"] }),
    // The overlay owner refreshes this expensive surface once on close.
    queryClient.invalidateQueries({
      queryKey: ["prompt-registry-heatmap"],
      refetchType: "none",
    }),
  ]);
}
