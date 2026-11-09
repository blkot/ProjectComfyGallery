import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type HumanClassifierRating,
  type MediaSafetyClassificationBatch,
  type MediaSafetyClassificationStatus,
} from "../lib/api";
import { titleCase } from "../lib/format";

const reviewRatings: Array<{ value: HumanClassifierRating; label: string }> = [
  { value: "safe", label: "Safe" },
  { value: "sexy", label: "Sexy" },
  { value: "nudity", label: "Nudity" },
  { value: "explicit", label: "Explicit" },
];

const exposedDetectionClasses = new Set([
  "ANUS_EXPOSED",
  "BUTTOCKS_EXPOSED",
  "FEMALE_BREAST_EXPOSED",
  "FEMALE_GENITALIA_EXPOSED",
  "MALE_BREAST_EXPOSED",
  "MALE_GENITALIA_EXPOSED",
]);

export function MediaSafetyClassificationPanel({
  mediaId,
}: {
  mediaId: string;
}) {
  const queryClient = useQueryClient();
  const classification = useQuery({
    queryKey: ["media-safety-classification", mediaId],
    queryFn: () =>
      apiRequest<MediaSafetyClassificationStatus>(
        `/api/v1/media/${mediaId}/nsfw-classification`,
      ),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.job?.status ?? "")
        ? 2_000
        : false,
  });
  const classify = useMutation({
    mutationFn: () =>
      apiRequest<MediaSafetyClassificationBatch>(
        "/api/v1/media/bulk/nsfw-classification",
        {
          method: "POST",
          body: JSON.stringify({ media_ids: [mediaId], force: true }),
        },
      ),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["media-safety-classification", mediaId],
        }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
      ]);
    },
  });
  const saveReview = useMutation({
    mutationFn: (rating: HumanClassifierRating) =>
      apiRequest(`/api/v1/media/${mediaId}/classifier-review`, {
        method: "PUT",
        body: JSON.stringify({ rating }),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["media-safety-classification", mediaId],
        }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
      ]);
    },
  });
  const clearReview = useMutation({
    mutationFn: () =>
      apiRequest(`/api/v1/media/${mediaId}/classifier-review`, {
        method: "DELETE",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["media-safety-classification", mediaId],
        }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
      ]);
    },
  });

  const assessment = classification.data?.assessment;
  const humanReview = classification.data?.review;
  const jobStatus = classification.data?.job?.status;
  const busy = jobStatus === "queued" || jobStatus === "running";
  const reviewPending = saveReview.isPending || clearReview.isPending;
  const reviewError = saveReview.error ?? clearReview.error;
  const reviewRelationship =
    humanReview && assessment?.status === "completed" && assessment.suggested_rating
      ? humanReview.rating === assessment.suggested_rating
        ? "Confirms model result"
        : "Overrides model result"
      : null;

  function recordRating(rating: HumanClassifierRating) {
    saveReview.mutate(rating);
  }

  return (
    <section className="media-safety-classification" aria-labelledby="media-safety-title">
      <div className="media-safety-classification-heading">
        <div>
          <p className="kicker">Classifier</p>
          <h2 id="media-safety-title">Content classification</h2>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={busy || classify.isPending}
          onClick={() => classify.mutate()}
        >
          {busy || classify.isPending
            ? "Classification queued"
            : assessment?.status === "completed"
              ? "Run again"
              : "Classify image"}
        </button>
      </div>

      {classify.error ? (
        <p className="notice error-notice" role="alert">
          {classify.error.message}
        </p>
      ) : classification.error ? (
        <p className="notice error-notice" role="alert">
          Classification status could not be loaded.
        </p>
      ) : classification.isPending ? (
        <p className="muted">Loading classification…</p>
      ) : busy ? (
        <p className="muted">
          {jobStatus === "queued" ? "Waiting for the classifier…" : "Classifying image…"}
        </p>
      ) : assessment?.status === "failed" ? (
        <p className="notice error-notice" role="alert">
          {assessment.error_message ?? "Classification failed."}
        </p>
      ) : assessment?.status === "completed" ? (
        <>
          <p
            className="media-safety-suggestion"
            data-review={assessment.needs_review || undefined}
          >
            Model result: {titleCase(assessment.label ?? "unknown")}
            {assessment.confidence !== null
              ? ` · ${(assessment.confidence * 100).toFixed(1)}%`
              : ""}
            {assessment.suggested_rating
              ? ` · Rating: ${titleCase(assessment.suggested_rating)}`
              : ""}
          </p>
          {assessment.needs_review && !humanReview ? (
            <p className="media-safety-review-note">
              Model confidence is low; a human review is recommended but optional.
            </p>
          ) : null}
          <div
            className="media-safety-scores"
            role="list"
            aria-label="Classifier confidence scores"
          >
            {Object.entries(assessment.scores)
              .sort(([, first], [, second]) => second - first)
              .map(([label, score]) => {
                const predicted =
                  label.trim().toLowerCase() === assessment.label?.trim().toLowerCase();
                return (
                  <div
                    className="media-safety-score"
                    data-severity={scoreSeverity(label)}
                    data-predicted={predicted || undefined}
                    key={label}
                    role="listitem"
                    aria-current={predicted ? "true" : undefined}
                  >
                    <span className="media-safety-score-heading">
                      <span>{titleCase(label)}</span>
                      {predicted ? (
                        <span className="media-safety-score-predicted">Model result</span>
                      ) : null}
                    </span>
                    <strong>{(score * 100).toFixed(1)}%</strong>
                  </div>
                );
              })}
          </div>
          {assessment.nudity_detector_status === "completed" ? (
            <div className="media-safety-nudity-evidence">
              <p className="kicker">Detected regions</p>
              {assessment.nudity_detections.length ? (
                <ul>
                  {assessment.nudity_detections.slice(0, 8).map((detection, index) => {
                    const detectionClass = detection.class.toUpperCase();
                    const critical = exposedDetectionClasses.has(detectionClass);
                    return (
                      <li key={`${detectionClass}-${index}`}>
                        <span
                          className="nudity-evidence-chip"
                          data-critical={critical || undefined}
                          data-pattern={!critical || undefined}
                        >
                          <span>
                            {titleCase(detectionClass.toLowerCase().replaceAll("_", " "))}
                          </span>
                          <strong>{(detection.score * 100).toFixed(1)}%</strong>
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="muted">No exposed-region detections</p>
              )}
            </div>
          ) : null}
        </>
      ) : (
        <p className="muted">No model result yet.</p>
      )}

      <div className="media-safety-human-review">
        <div className="media-safety-human-review-heading">
          <div>
            <p className="kicker">Human review (optional)</p>
            {humanReview ? (
              <p className="media-safety-recorded-rating">
                Human rating: <strong>{titleCase(humanReview.rating)}</strong>
                {reviewRelationship ? ` · ${reviewRelationship}` : ""}
              </p>
            ) : (
              <p className="media-safety-review-note">
                {assessment?.status === "completed"
                  ? "The model result remains active until you record a human rating here."
                  : "Choose a rating only if you want to record a human decision."}
              </p>
            )}
          </div>
          {humanReview ? (
            <button
              className="text-button"
              type="button"
              disabled={reviewPending}
              onClick={() => clearReview.mutate()}
            >
              Undo rating
            </button>
          ) : null}
        </div>
        <div className="media-safety-rating-buttons" role="group" aria-label="Human rating">
          {reviewRatings.map((rating) => (
            <button
              className="media-safety-rating-button"
              data-rating={rating.value}
              data-selected={humanReview?.rating === rating.value || undefined}
              type="button"
              key={rating.value}
              disabled={reviewPending || classification.isPending}
              aria-pressed={humanReview?.rating === rating.value}
              onClick={() => recordRating(rating.value)}
            >
              {rating.label}
            </button>
          ))}
        </div>
        {reviewError ? (
          <p className="notice error-notice" role="alert">
            {reviewError.message}
          </p>
        ) : null}
      </div>
    </section>
  );
}

function scoreSeverity(label: string): "safe" | "suggestive" | "explicit" | "unknown" {
  switch (label.trim().toLowerCase()) {
    case "normal":
    case "drawing":
      return "safe";
    case "sexy":
      return "suggestive";
    case "porn":
    case "hentai":
      return "explicit";
    default:
      return "unknown";
  }
}
