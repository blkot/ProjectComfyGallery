import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { RefObject } from "react";

import {
  apiRequest,
  type ContentRating,
  type MediaContentRating,
  type MediaDetail,
  type MediaPage,
} from "../lib/api";

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
}: {
  mediaId: string;
  rating: ContentRating;
  className?: string;
  shortcutButtonRef?: RefObject<HTMLButtonElement | null>;
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
        queryClient.invalidateQueries({ queryKey: ["photo-wall"] }),
      ]);
    },
  });

  return (
    <div
      className={`media-content-rating-control ${className}`.trim()}
      role="group"
      aria-label="Content safety rating"
      data-rating={rating}
    >
      {ratingOptions.map((option) => (
        <button
          ref={
            option.value === "nsfw" && rating !== "nsfw"
              ? shortcutButtonRef
              : undefined
          }
          className="media-content-rating-option"
          data-rating={option.value}
          type="button"
          aria-pressed={rating === option.value}
          aria-label={option.label}
          aria-keyshortcuts={option.value === "nsfw" ? "N" : undefined}
          disabled={mutation.isPending}
          key={option.value}
          title={option.value === "nsfw" ? "Mark NSFW (N)" : option.label}
          onClick={() => mutation.mutate(option.value)}
        >
          {option.label}
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
