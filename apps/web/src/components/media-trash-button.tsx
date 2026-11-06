import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type Evaluation,
  type MediaDetail,
  type MediaEvaluationContext,
  type MediaPage,
} from "../lib/api";
import { refreshMediaMutationCaches } from "../lib/media-mutation-cache";
import { MediaActionIcon } from "./media-action-icon";

export function MediaTrashButton({
  mediaId,
  isTrash,
  compact = false,
  className = "",
}: {
  mediaId: string;
  isTrash: boolean;
  compact?: boolean;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const contextKey = ["media-evaluation-context", mediaId] as const;
  const mutation = useMutation({
    mutationFn: async (restore: boolean) => {
      const context = await apiRequest<MediaEvaluationContext>(
        `/api/v1/media/${mediaId}/evaluation-context`,
        { method: "POST" },
      );
      queryClient.setQueryData(contextKey, context);
      const baseEvaluation = context.evaluations.find(
        (evaluation) => evaluation.evaluation_kind === "base",
      );
      if (!baseEvaluation) {
        throw new Error("Trash is not available for this media.");
      }
      return apiRequest<Evaluation>(
        `/api/v1/evaluations/${baseEvaluation.id}/${restore ? "restore" : "trash"}`,
        {
          method: "POST",
          body: JSON.stringify({ expected_version: baseEvaluation.version }),
        },
      );
    },
    onSuccess: async (updated) => {
      queryClient.setQueryData<MediaEvaluationContext>(contextKey, (current) =>
        current
          ? {
              ...current,
              is_trash: updated.is_trash,
              evaluations: current.evaluations.map((evaluation) =>
                evaluation.id === updated.id ? updated : evaluation,
              ),
            }
          : current,
      );
      queryClient.setQueryData<MediaDetail>(
        ["media-detail", mediaId],
        (current) =>
          current ? { ...current, is_trash: updated.is_trash } : current,
      );
      queryClient.setQueriesData<MediaPage>(
        { queryKey: ["media"] },
        (current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) =>
                  item.id === mediaId
                    ? { ...item, is_trash: updated.is_trash }
                    : item,
                ),
              }
            : current,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
        queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["review-sessions"] }),
        queryClient.invalidateQueries({ queryKey: ["review-item"] }),
        refreshMediaMutationCaches(queryClient, mediaId, { is_trash: updated.is_trash }),
      ]);
    },
  });
  const label = isTrash ? "Restore from Trash" : "Move to Trash";
  const description = isTrash ? "In Trash — Restore media" : "Move to Trash";

  return (
    <span className="media-trash-action">
      <button
        className={`media-trash-button ${className}`.trim()}
        type="button"
        aria-label={label}
        data-trashed={isTrash || undefined}
        data-action={isTrash ? "restore" : "trash"}
        data-compact={compact || undefined}
        disabled={mutation.isPending}
        title={mutation.isError ? `${description} — update failed` : description}
        onClick={() => mutation.mutate(isTrash)}
      >
        {compact ? <>
          <MediaActionIcon name={isTrash ? "restore" : "trash"} />
          {isTrash ? <span className="media-trash-restore-label" aria-hidden="true">Restore</span> : null}
        </> : mutation.isPending ? "Updating…" : isTrash ? "Restore" : "Trash"}
      </button>
      {mutation.isError ? (
        <span className="sr-only" role="alert">
          {mutation.error.message}
        </span>
      ) : null}
    </span>
  );
}
