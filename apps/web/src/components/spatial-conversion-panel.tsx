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
  pollInterval?: number;
};

const activeStatuses = new Set(["queued", "submitting", "processing"]);

function readableError(error: Error | null) {
  if (!error) return null;
  if (error instanceof ApiClientError) return `${error.code}: ${error.message}`;
  return "The spatial conversion request could not be started.";
}

export function SpatialConversionPanel({
  mediaId,
  hasVariant,
  pollInterval = 3_000,
}: SpatialConversionPanelProps) {
  const queryClient = useQueryClient();
  const refreshedRun = useRef<string | null>(null);
  const state = useQuery({
    queryKey: ["spatial-conversion", mediaId],
    queryFn: () =>
      apiRequest<SpatialConversionState>(
        `/api/v1/media/${mediaId}/spatial-conversions/current`,
      ),
    refetchInterval: (query) => {
      const status = query.state.data?.conversion?.status;
      return status && activeStatuses.has(status) ? pollInterval : false;
    },
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
  const error = readableError(start.error);

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
            You can leave this page; the server will keep tracking the job.
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
      {error ? (
        <p className="notice error-notice" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
