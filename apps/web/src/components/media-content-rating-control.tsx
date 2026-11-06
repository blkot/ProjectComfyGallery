import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { RefObject } from "react";

import {
  apiRequest,
  type ContentRating,
  type MediaContentRating,
  type MediaDetail,
  type MediaPage,
} from "../lib/api";
import { refreshMediaMutationCaches } from "../lib/media-mutation-cache";

const ratingOptions: ReadonlyArray<{
  value: ContentRating;
  label: string;
}> = [
  { value: "sfw", label: "SFW" },
  { value: "nsfw", label: "NSFW" },
];

export function MediaContentRatingControl({
  mediaId,
  rating,
  className = "",
  shortcutButtonRef,
  compact = false,
}: {
  mediaId: string;
  rating: ContentRating;
  className?: string;
  shortcutButtonRef?: RefObject<HTMLButtonElement | null>;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: (contentRating: ContentRating) =>
      apiRequest<MediaContentRating>(
        `/api/v1/media/${mediaId}/content-rating`,
        {
          method: "PUT",
          body: JSON.stringify({ content_rating: contentRating }),
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
                    ? { ...item, content_rating: response.content_rating }
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
                content_rating: response.content_rating,
                updated_at: response.updated_at,
              }
            : current,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
        refreshMediaMutationCaches(queryClient, mediaId, { content_rating: response.content_rating }),
      ]);
    },
  });

  return (
    <div
      className={`media-content-rating-control ${className}`.trim()}
      role="group"
      aria-label="Content safety rating"
      data-rating={rating}
      data-compact={compact || undefined}
    >
      {ratingOptions.map((option) => (
        <button
          ref={
            option.value !== rating
              ? shortcutButtonRef
              : undefined
          }
          className="media-content-rating-option"
          data-rating={option.value}
          type="button"
          aria-pressed={rating === option.value}
          aria-label={option.label}
          aria-keyshortcuts={option.value !== rating ? "N" : undefined}
          disabled={mutation.isPending}
          key={option.value}
          title={`${option.value === "nsfw" ? "Restricted (NSFW)" : "Normal (SFW)"}${option.value !== rating ? " · N" : ""}`}
          onClick={() => mutation.mutate(option.value)}
        >
          {compact ? (option.value === "sfw" ? "N" : "R") : option.label}
        </button>
      ))}
      {mutation.isError ? (
        <span className="sr-only" role="alert">
          {mutation.error.message}
        </span>
      ) : null}
    </div>
  );
}
