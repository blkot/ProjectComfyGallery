import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type MediaDetail,
  type MediaFavorite,
  type MediaPage,
} from "../lib/api";

export function MediaFavoriteButton({
  mediaId,
  favorite,
  className = "",
}: {
  mediaId: string;
  favorite: boolean;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (nextFavorite: boolean) =>
      apiRequest<MediaFavorite>(`/api/v1/media/${mediaId}/favorite`, {
        method: "PUT",
        body: JSON.stringify({ favorite: nextFavorite }),
      }),
    onSuccess: async (response) => {
      queryClient.setQueriesData<MediaPage>(
        { queryKey: ["media"] },
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) =>
                  item.id === mediaId
                    ? { ...item, favorite: response.favorite }
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
                favorite: response.favorite,
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
  const label = favorite ? "Remove from favorites" : "Add to favorites";

  return (
    <button
      className={`media-favorite-button ${className}`.trim()}
      type="button"
      aria-label={label}
      aria-pressed={favorite}
      disabled={mutation.isPending}
      data-error={mutation.isError || undefined}
      title={mutation.isError ? `${label} — update failed` : label}
      onClick={() => mutation.mutate(!favorite)}
    >
      <span aria-hidden="true">{favorite ? "★" : "☆"}</span>
    </button>
  );
}
