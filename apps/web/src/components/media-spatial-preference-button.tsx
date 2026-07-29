import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type MediaDetail,
  type MediaPage,
  type MediaPlaybackPreference,
} from "../lib/api";

export function MediaSpatialPreferenceButton({
  mediaId,
  preferred,
  className = "",
}: {
  mediaId: string;
  preferred: boolean;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (preferSpatialPlayback: boolean) =>
      apiRequest<MediaPlaybackPreference>(
        `/api/v1/media/${mediaId}/playback-preference`,
        {
          method: "PUT",
          body: JSON.stringify({
            prefer_spatial_playback: preferSpatialPlayback,
          }),
        },
      ),
    onSuccess: async (response) => {
      queryClient.setQueriesData<MediaPage>(
        { queryKey: ["media"] },
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) =>
                  item.id === mediaId
                    ? {
                        ...item,
                        prefer_spatial_playback:
                          response.prefer_spatial_playback,
                        spatial_view_preferred:
                          response.spatial_view_preferred,
                      }
                    : item,
                ),
              }
            : current,
      );
      queryClient.setQueryData<MediaDetail>(
        ["media-detail", mediaId],
        (current) =>
          current
            ? {
                ...current,
                prefer_spatial_playback: response.prefer_spatial_playback,
                spatial_view_preferred: response.spatial_view_preferred,
                updated_at: response.updated_at,
              }
            : current,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
      ]);
    },
  });
  const action = preferred
    ? "Use standard playback when possible"
    : "Prefer spatial playback when available";

  return (
    <button
      className={`spatial-preference-button ${className}`.trim()}
      type="button"
      aria-label={action}
      aria-pressed={preferred}
      disabled={mutation.isPending}
      data-error={mutation.isError || undefined}
      title={mutation.isError ? `${action} — update failed` : action}
      onClick={() => mutation.mutate(!preferred)}
    >
      <span aria-hidden="true">◉</span>
      {preferred ? "Spatial preferred" : "Standard preferred"}
    </button>
  );
}
