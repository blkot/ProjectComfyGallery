import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  ApiClientError,
  apiRequest,
  type WorkflowInputList,
  type WorkflowInputReference,
  type WorkflowInputResolveAccepted,
} from "../lib/api";
import { formatBytes, formatDuration, titleCase } from "../lib/format";

type WorkflowInputMediaProps = {
  mediaId: string;
};

const activeStatuses = new Set(["pending", "resolving"]);
const statusLabels: Record<string, string> = {
  failed: "Capture failed",
  missing: "Missing from ComfyUI",
  pending: "Waiting for capture",
  ready: "Ready",
  resolving: "Capturing",
  unavailable: "Unavailable",
};

export function WorkflowInputMedia({ mediaId }: WorkflowInputMediaProps) {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState<string | null>(null);
  const inputs = useQuery({
    queryKey: ["workflow-inputs", mediaId],
    queryFn: () =>
      apiRequest<WorkflowInputList>(
        `/api/v1/media/${mediaId}/workflow-inputs`,
      ),
    enabled: Boolean(mediaId),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((item) => activeStatuses.has(item.status))
        ? 2_000
        : false;
    },
  });
  const resolve = useMutation({
    mutationFn: () =>
      apiRequest<WorkflowInputResolveAccepted>(
        `/api/v1/media/${mediaId}/workflow-inputs/resolve`,
        { method: "POST" },
      ),
    onMutate: () => setNotice(null),
    onSuccess: async (response) => {
      setNotice(
        `Capture queued (${titleCase(response.job.status)}). This panel will update when processing finishes.`,
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workflow-inputs", mediaId] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });

  if (inputs.isPending) {
    return (
      <section className="workflow-input-media" aria-labelledby="workflow-input-media-title">
        <WorkflowInputHeading />
        <p className="muted">Checking captured workflow inputs…</p>
      </section>
    );
  }

  if (inputs.isError || !inputs.data) {
    return (
      <section className="workflow-input-media" aria-labelledby="workflow-input-media-title">
        <WorkflowInputHeading />
        <p className="notice error-notice" role="alert">
          {inputs.error instanceof ApiClientError
            ? inputs.error.message
            : "Workflow input media could not be loaded."}
        </p>
        <button
          className="secondary-button"
          type="button"
          onClick={() => void inputs.refetch()}
        >
          Try again
        </button>
      </section>
    );
  }

  const data = inputs.data;
  const activeItems = data.items.filter((item) => activeStatuses.has(item.status));
  const retryableItems = data.items.filter(
    (item) => item.status !== "ready" && !activeStatuses.has(item.status),
  );
  const canResolve = retryableItems.length > 0 && !resolve.isPending;

  return (
    <section className="workflow-input-media" aria-labelledby="workflow-input-media-title">
      <header className="workflow-input-media-heading">
        <div>
          <p className="kicker">Captured provenance</p>
          <h2 id="workflow-input-media-title">Input media</h2>
        </div>
        <div className="workflow-input-media-actions">
          <span className="document-count">
            {data.ready_count} ready · {data.total} detected
          </span>
          {canResolve ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => resolve.mutate()}
            >
              Retry capture
            </button>
          ) : activeItems.length > 0 ? (
            <span className="workflow-input-media-progress">Capturing…</span>
          ) : null}
        </div>
      </header>

      {notice ? (
        <p className="notice workflow-input-media-notice" role="status">
          {notice}
        </p>
      ) : null}
      {resolve.error ? (
        <p className="notice error-notice" role="alert">
          {resolve.error instanceof ApiClientError
            ? `${resolve.error.code}: ${resolve.error.message}`
            : "Workflow input capture could not be queued."}
        </p>
      ) : null}

      {data.items.length === 0 ? (
        <div className="empty-state workflow-input-media-empty">
          <strong>No workflow input media detected</strong>
          <p>
            This workflow does not contain a recognized image or video input
            reference.
          </p>
        </div>
      ) : (
        <div className="workflow-input-media-list">
          {data.items.map((item) => (
            <WorkflowInputCard item={item} key={item.id} />
          ))}
        </div>
      )}
    </section>
  );
}

function WorkflowInputHeading() {
  return (
    <header className="workflow-input-media-heading">
      <div>
        <p className="kicker">Captured provenance</p>
        <h2 id="workflow-input-media-title">Input media</h2>
      </div>
    </header>
  );
}

function WorkflowInputCard({ item }: { item: WorkflowInputReference }) {
  const ready = item.status === "ready" && item.asset && item.content_url;
  const isVideo = Boolean(
    item.asset?.kind === "video" || item.asset?.mime_type.startsWith("video/"),
  );
  const sourcePath = [item.source_subfolder, item.source_filename]
    .filter(Boolean)
    .join("/");
  const provenance = [
    `Node ${item.original_node_id}`,
    item.class_type,
    item.input_name,
  ]
    .filter(Boolean)
    .join(" · ");
  const error = [item.last_error_code, item.last_error_message]
    .filter(Boolean)
    .join(": ");

  return (
    <article className="workflow-input-card" data-status={item.status}>
      <div className="workflow-input-preview">
        {ready ? (
          isVideo ? (
            <video
              src={item.content_url ?? undefined}
              controls
              preload="metadata"
              aria-label={`Workflow input ${item.source_filename}`}
            />
          ) : (
            <img
              src={item.content_url ?? undefined}
              alt={`Workflow input ${item.source_filename}`}
              loading="lazy"
            />
          )
        ) : (
          <span>{statusLabel(item.status)}</span>
        )}
      </div>
      <div className="workflow-input-card-body">
        <div className="workflow-input-card-heading">
          <strong title={sourcePath}>{item.source_filename}</strong>
          <span className="status-chip" data-status={item.status}>
            {statusLabel(item.status)}
          </span>
        </div>
        <small className="workflow-input-source" title={sourcePath}>
          {sourcePath} · {titleCase(item.source_type)}
        </small>
        <small className="workflow-input-provenance">{provenance}</small>
        {item.asset ? <InputAssetFacts item={item} /> : null}
        {error ? (
          <p className="workflow-input-error">
            {error}
          </p>
        ) : null}
      </div>
    </article>
  );
}

function InputAssetFacts({ item }: { item: WorkflowInputReference }) {
  const asset = item.asset;
  if (!asset) return null;
  const dimensions =
    asset.width && asset.height ? `${asset.width} × ${asset.height}` : null;
  const facts = [
    dimensions,
    asset.duration_seconds !== null
      ? formatDuration(asset.duration_seconds)
      : null,
    asset.detected_format || asset.mime_type,
    formatBytes(asset.byte_size),
  ].filter(Boolean);
  return <small className="workflow-input-facts">{facts.join(" · ")}</small>;
}

function statusLabel(status: string) {
  return statusLabels[status] ?? titleCase(status);
}
