import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type MediaSafetyClassificationBatch,
  type MediaSafetyClassificationStatus,
} from "../lib/api";
import { titleCase } from "../lib/format";

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

  const assessment = classification.data?.assessment;
  const jobStatus = classification.data?.job?.status;
  const busy = jobStatus === "queued" || jobStatus === "running";

  return (
    <section className="media-safety-classification" aria-labelledby="media-safety-title">
      <div className="media-safety-classification-heading">
        <div>
          <p className="kicker">AI suggestion</p>
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
        <p className="muted">Loading classification status…</p>
      ) : busy ? (
        <p className="muted">
          {jobStatus === "queued" ? "Waiting for the classifier…" : "Classifying image…"}
          The model process stops after its idle timeout.
        </p>
      ) : assessment?.status === "failed" ? (
        <p className="notice error-notice" role="alert">
          {assessment.error_message ?? "Classification failed."}
        </p>
      ) : assessment?.status === "completed" ? (
        <>
          <p className="media-safety-suggestion" data-review={assessment.needs_review || undefined}>
            {assessment.needs_review
              ? "Needs human review"
              : `Suggested: ${titleCase(assessment.suggested_rating ?? assessment.label ?? "unknown")}`}
            {assessment.confidence !== null
              ? ` · ${(assessment.confidence * 100).toFixed(1)}% confidence`
              : ""}
          </p>
          <p className="muted">
            Model label: {titleCase(assessment.label ?? "unknown")} · {assessment.model_id}
            {` · ${assessment.inference_backend.toUpperCase()}`}
          </p>
          <dl className="media-safety-scores">
            {Object.entries(assessment.scores)
              .sort(([, first], [, second]) => second - first)
              .map(([label, score]) => (
                <div key={label}>
                  <dt>{titleCase(label)}</dt>
                  <dd>{(score * 100).toFixed(1)}%</dd>
                </div>
              ))}
          </dl>
          {assessment.nudity_detector_status === "completed" ? (
            <div className="media-safety-nudity-evidence">
              <p className="muted">
                NudeNet: {assessment.nudity_detected ? "exposed-region evidence found" : "no qualifying exposed regions"}
                {assessment.nudity_model_revision
                  ? ` · ${assessment.nudity_model_revision}`
                  : ""}
              </p>
              {assessment.nudity_detections.length ? (
                <ul>
                  {assessment.nudity_detections.slice(0, 8).map((detection, index) => (
                    <li key={`${detection.class}-${index}`}>
                      {titleCase(detection.class)} · {(detection.score * 100).toFixed(1)}%
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : assessment.nudity_detector_status === "skipped" ? (
            <p className="muted">NudeNet was skipped by the configured low-resource mode.</p>
          ) : null}
          <small className="muted">
            This is a model suggestion. The human SFW/NSFW rating remains unchanged.
          </small>
        </>
      ) : (
        <p className="muted">
          No AI result yet. Classification runs only after an upload or when you start it.
        </p>
      )}
    </section>
  );
}
