import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { RefObject } from "react";

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
  buttonRef,
  showLabel = false,
}: {
  mediaId: string;
  favorite: boolean;
  className?: string;
  buttonRef?: RefObject<HTMLButtonElement | null>;
  showLabel?: boolean;
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
      ref={buttonRef}
      className={`media-favorite-button ${className}`.trim()}
      type="button"
      aria-label={label}
      aria-pressed={favorite}
      data-labeled={showLabel || undefined}
      disabled={mutation.isPending}
      data-error={mutation.isError || undefined}
      title={mutation.isError ? `${label} — update failed` : label}
      onClick={() => mutation.mutate(!favorite)}
    >
      <span className="media-favorite-glyph" aria-hidden="true">
        {favorite ? "★" : "☆"}
      </span>
      {showLabel ? (
        <span className="media-favorite-text" aria-hidden="true">
          {favorite ? "Favorited" : "Favorite"}
        </span>
      ) : null}
    </button>
  );
}
