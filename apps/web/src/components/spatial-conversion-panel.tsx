import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import {
  ApiClientError,
  apiRequest,
  type SpatialConversionState,
} from "../lib/api";
import { titleCase } from "../lib/format";

type SpatialConversionPanelProps = {
  mediaId: string;
  hasVariant: boolean;
};

const activeStatuses = new Set(["queued", "submitting", "processing"]);
const refreshObservationAttempts = 6;
const refreshObservationIntervalMs = 500;

function delay(milliseconds: number) {
  return new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));
}

async function observeScheduledRefresh(
  mediaId: string,
  accepted: SpatialConversionState,
) {
  const baseline = accepted.conversion;
  if (!baseline || !activeStatuses.has(baseline.status)) return accepted;

  let latest = accepted;
  for (let attempt = 0; attempt < refreshObservationAttempts; attempt += 1) {
    latest = await apiRequest<SpatialConversionState>(
      `/api/v1/media/${mediaId}/spatial-conversions/current`,
    );
    const current = latest.conversion;
    if (
      !current ||
      current.id !== baseline.id ||
      !activeStatuses.has(current.status) ||
      current.last_reconciled_at !== baseline.last_reconciled_at
    ) {
      return latest;
    }
    if (attempt + 1 < refreshObservationAttempts) {
      await delay(refreshObservationIntervalMs);
    }
  }
  return latest;
}

function readableError(error: Error | null) {
  if (!error) return null;
  if (error instanceof ApiClientError) return `${error.code}: ${error.message}`;
  return "The spatial conversion request could not be started.";
}

export function SpatialConversionPanel({
  mediaId,
  hasVariant,
}: SpatialConversionPanelProps) {
  const queryClient = useQueryClient();
  const refreshedRun = useRef<string | null>(null);
  const state = useQuery({
    queryKey: ["spatial-conversion", mediaId],
    queryFn: () =>
      apiRequest<SpatialConversionState>(
        `/api/v1/media/${mediaId}/spatial-conversions/current`,
      ),
    // MSS publishes the authoritative completion event to CG.  Detail refresh is
    // on-demand; this browser never becomes a high-frequency conversion watcher.
    refetchInterval: false,
  });
  const start = useMutation({
    mutationFn: async () => {
      const retryable = state.data?.job?.error_details.retryable === true;
      if (state.data?.conversion?.status === "failed" && state.data.job && retryable) {
        await apiRequest(`/api/v1/jobs/${state.data.job.id}/retry`, {
          method: "POST",
        });
        return apiRequest<SpatialConversionState>(
          `/api/v1/media/${mediaId}/spatial-conversions/current`,
        );
      }
      return apiRequest<SpatialConversionState>(
        `/api/v1/media/${mediaId}/spatial-conversions`,
        { method: "POST", body: JSON.stringify({}) },
      );
    },
    onSuccess: async (response) => {
      queryClient.setQueryData(["spatial-conversion", mediaId], response);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const conversion = state.data?.conversion;
  const active = conversion ? activeStatuses.has(conversion.status) : false;
  const refresh = useMutation({
    mutationFn: async () => {
      const accepted = await apiRequest<SpatialConversionState>(
        `/api/v1/spatial-conversions/${conversion?.id}/refresh`,
        { method: "POST" },
      );
      // The 202 only confirms dispatch. Brief, bounded observation ensures the
      // first stale read cannot prematurely end this explicit user refresh.
      return observeScheduledRefresh(mediaId, accepted);
    },
    onSuccess: (response) =>
      queryClient.setQueryData(["spatial-conversion", mediaId], response),
  });
  const retryPublish = useMutation({
    mutationFn: async () => {
      await apiRequest<SpatialConversionState>(
        `/api/v1/spatial-conversions/${conversion?.id}/retry-publish`,
        { method: "POST" },
      );
      await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
      return apiRequest<SpatialConversionState>(
        `/api/v1/media/${mediaId}/spatial-conversions/current`,
      );
    },
    onSuccess: (response) =>
      queryClient.setQueryData(["spatial-conversion", mediaId], response),
  });

  useEffect(() => {
    if (
      conversion?.status !== "succeeded" ||
      refreshedRun.current === conversion.id
    ) {
      return;
    }
    refreshedRun.current = conversion.id;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
      queryClient.invalidateQueries({ queryKey: ["media"] }),
      queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    ]);
  }, [conversion?.id, conversion?.status, mediaId, queryClient]);

  if (state.isPending) {
    return (
      <div className="spatial-conversion-panel">
        <p className="muted">Checking spatial conversion service…</p>
      </div>
    );
  }

  if (state.isError) {
    return (
      <div className="spatial-conversion-panel">
        <p className="notice error-notice">{readableError(state.error)}</p>
      </div>
    );
  }

  const configured = state.data?.configured ?? false;
  const failed = conversion?.status === "failed";
  const actionLabel = active
    ? "Conversion in progress"
    : failed
      ? "Retry spatial conversion"
      : hasVariant
        ? "Generate replacement"
        : "Generate spatial video";
  const error = readableError(start.error) ?? readableError(refresh.error) ?? readableError(retryPublish.error);
  return (
    <section className="spatial-conversion-panel" aria-label="Spatial conversion">
      <div className="spatial-conversion-heading">
        <div>
          <strong>Generate with ml-sharp-spatial</strong>
          <small>
            ComfyGallery sends the original to MSS and attaches the validated result here.
          </small>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={!configured || active || start.isPending}
          onClick={() => start.mutate()}
        >
          {start.isPending ? "Starting…" : actionLabel}
        </button>
        {active ? (
          <button
            className="secondary-button"
            type="button"
            disabled={refresh.isPending}
            onClick={() => refresh.mutate()}
          >
            {refresh.isPending ? "Refreshing…" : "Refresh status"}
          </button>
        ) : null}
        {conversion?.publish_status === "failed" || conversion?.publish_status === "skipped" ? (
          <button
            className="secondary-button"
            type="button"
            disabled={retryPublish.isPending}
            onClick={() => retryPublish.mutate()}
          >
            {retryPublish.isPending ? "Retrying publication…" : "Retry publication"}
          </button>
        ) : null}
      </div>

      {!configured ? (
        <p className="notice">
          MSS is not configured on this ComfyGallery server. Set CG_MSS_BASE_URL to enable
          conversion.
        </p>
      ) : null}
      {active ? (
        <p className="notice spatial-variant-progress" role="status">
          <strong>{titleCase(conversion?.status ?? "processing")}</strong>
          <span>
            {conversion?.queue_position != null
              ? `MSS queue position: ${conversion.queue_position}. `
              : ""}
            Submission is complete; MSS runs independently and CG reconciles progress.
          </span>
        </p>
      ) : null}
      {conversion?.status === "succeeded" ? (
        <p className="notice spatial-variant-success" role="status">
          <strong>Spatial video ready</strong>
          <span>The spatial variant is attached to this media record.</span>
        </p>
      ) : null}
      {failed ? (
        <p className="notice error-notice" role="alert">
          <strong>Spatial conversion failed</strong>
          <span>
            {[conversion.error_code, conversion.error_message].filter(Boolean).join(": ")}
          </span>
        </p>
      ) : null}
      {conversion?.publish_status === "failed" || conversion?.publish_status === "skipped" ? (
        <p className="notice error-notice" role="alert">
          <strong>Spatial result is waiting to publish</strong>
          <span>
            {[conversion.error_code, conversion.error_message].filter(Boolean).join(": ")}
          </span>
        </p>
      ) : null}
      {error ? (
        <p className="notice error-notice" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
