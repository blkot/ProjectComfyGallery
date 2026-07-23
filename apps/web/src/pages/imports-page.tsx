import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useRef, useState } from "react";
import { Link } from "react-router-dom";

import {
  ApiClientError,
  apiRequest,
  type ScanBatch,
  type SourceRoot,
  type UploadBatch,
  type WorkflowBulkReprocessResult,
} from "../lib/api";
import { formatDate, titleCase } from "../lib/format";

const sourceRootsKey = ["source-roots"] as const;
const scansKey = ["scans"] as const;
const importsKey = ["imports"] as const;

export function ImportsPage() {
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [rootName, setRootName] = useState("");
  const [rootPath, setRootPath] = useState("/imports");

  const roots = useQuery({
    queryKey: sourceRootsKey,
    queryFn: () => apiRequest<SourceRoot[]>("/api/v1/source-roots"),
  });
  const scans = useQuery({
    queryKey: scansKey,
    queryFn: () => apiRequest<ScanBatch[]>("/api/v1/scans?limit=20"),
    refetchInterval: 3_000,
  });
  const batches = useQuery({
    queryKey: importsKey,
    queryFn: () => apiRequest<UploadBatch[]>("/api/v1/imports?limit=12"),
    refetchInterval: 3_000,
  });

  const upload = useMutation({
    mutationFn: async () => {
      const body = new FormData();
      selectedFiles.forEach((file) => body.append("files", file));
      return apiRequest<UploadBatch>("/api/v1/media/imports", {
        method: "POST",
        body,
      });
    },
    onSuccess: async () => {
      setSelectedFiles([]);
      if (fileInput.current) fileInput.current.value = "";
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: importsKey }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });
  const createRoot = useMutation({
    mutationFn: () =>
      apiRequest<SourceRoot>("/api/v1/source-roots", {
        method: "POST",
        body: JSON.stringify({ name: rootName, path: rootPath }),
      }),
    onSuccess: async () => {
      setRootName("");
      await queryClient.invalidateQueries({ queryKey: sourceRootsKey });
    },
  });
  const startScan = useMutation({
    mutationFn: (rootId: string) =>
      apiRequest<ScanBatch>(`/api/v1/source-roots/${rootId}/scans`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: scansKey }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });
  const reprocessMissing = useMutation({
    mutationFn: () =>
      apiRequest<WorkflowBulkReprocessResult>("/api/v1/workflows/reprocess", {
        method: "POST",
        body: JSON.stringify({ mode: "missing" }),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
        queryClient.invalidateQueries({ queryKey: ["media"] }),
      ]);
    },
  });

  function submitRoot(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createRoot.mutate();
  }

  const mutationError =
    upload.error ?? createRoot.error ?? startScan.error ?? reprocessMissing.error;

  return (
    <main className="page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Ingestion control</p>
          <h1>Import media</h1>
          <p className="muted">
            Browser uploads enter staging first. NAS scans read only from configured
            server mounts and skip unchanged paths on later runs.
          </p>
        </div>
        <Link className="secondary-button link-button" to="/jobs">
          View jobs
        </Link>
      </header>

      {mutationError ? (
        <p className="notice error-notice" role="alert">
          {mutationError instanceof ApiClientError
            ? mutationError.message
            : "The import action failed."}
        </p>
      ) : null}

      <section className="import-grid">
        <article className="panel import-panel">
          <p className="kicker">One-off import</p>
          <h2>Upload from browser</h2>
          <p className="muted">
            Best for a selected group. Up to 200 files per batch; processing continues
            in the worker after reception finishes.
          </p>
          <label className="file-drop">
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp,video/mp4,video/webm"
              multiple
              onChange={(event) => setSelectedFiles(Array.from(event.target.files ?? []))}
            />
            <strong>
              {selectedFiles.length
                ? `${selectedFiles.length} file(s) selected`
                : "Choose images or videos"}
            </strong>
            <small>PNG, JPEG, WebP, MP4, or WebM</small>
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={!selectedFiles.length || upload.isPending}
            onClick={() => upload.mutate()}
          >
            {upload.isPending ? "Receiving files…" : "Start upload"}
          </button>
        </article>

        <article className="panel import-panel">
          <p className="kicker">Repeatable source</p>
          <h2>Register a NAS directory</h2>
          <p className="muted">
            Use the path visible inside the container, normally <code>/imports</code> or
            one of its subdirectories.
          </p>
          <form className="compact-form" onSubmit={submitRoot}>
            <label>
              Source name
              <input
                value={rootName}
                maxLength={128}
                placeholder="Existing ComfyUI output"
                required
                onChange={(event) => setRootName(event.target.value)}
              />
            </label>
            <label>
              Container path
              <input
                value={rootPath}
                maxLength={1024}
                required
                onChange={(event) => setRootPath(event.target.value)}
              />
            </label>
            <button
              className="secondary-button"
              type="submit"
              disabled={createRoot.isPending}
            >
              {createRoot.isPending ? "Registering…" : "Register source"}
            </button>
          </form>
        </article>
      </section>

      <section className="panel workflow-backfill-panel section-block">
        <div>
          <p className="kicker">Phase 2 backfill</p>
          <h2>Extract existing workflows</h2>
          <p className="muted">
            Queue metadata extraction only for media imported before workflow support.
            Originals are read from managed storage and never rewritten.
          </p>
        </div>
        <div>
          {reprocessMissing.data ? (
            <small>
              {reprocessMissing.data.queued_count} queued ·{" "}
              {reprocessMissing.data.already_active_count} already active ·{" "}
              {reprocessMissing.data.queue_failed_count} queue failures
            </small>
          ) : null}
          <button
            className="secondary-button"
            type="button"
            disabled={reprocessMissing.isPending}
            onClick={() => reprocessMissing.mutate()}
          >
            {reprocessMissing.isPending
              ? "Queuing extraction…"
              : "Process unparsed media"}
          </button>
        </div>
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="kicker">Source registry</p>
            <h2>Directories</h2>
          </div>
          <span className="document-count">{roots.data?.length ?? 0} registered</span>
        </div>
        <div className="record-list">
          {roots.data?.map((root) => {
            const active = scans.data?.some(
              (scan) =>
                scan.source_root_id === root.id &&
                ["queued", "running"].includes(scan.status),
            );
            return (
              <article className="record-row" key={root.id}>
                <div>
                  <strong>{root.name}</strong>
                  <code>{root.path}</code>
                  <small>Last scan: {formatDate(root.last_scan_at)}</small>
                </div>
                <button
                  className="secondary-button"
                  type="button"
                  disabled={!root.enabled || active || startScan.isPending}
                  onClick={() => startScan.mutate(root.id)}
                >
                  {active ? "Scanning…" : "Scan for changes"}
                </button>
              </article>
            );
          })}
          {roots.data?.length === 0 ? (
            <div className="empty-state">
              <strong>No source directories</strong>
              <p>Register a path from an allowed read-only import mount.</p>
            </div>
          ) : null}
        </div>
      </section>

      <section className="history-grid section-block">
        <HistoryPanel title="Recent scans">
          {scans.data?.map((scan) => (
            <div className="history-row" key={scan.id}>
              <span>
                <strong>{titleCase(scan.status)}</strong>
                <small>{formatDate(scan.created_at)}</small>
              </span>
              <span className="history-counts">
                {scan.imported_count} new · {scan.duplicate_count} duplicate ·{" "}
                {scan.skipped_count} skipped · {scan.failed_count} failed
              </span>
            </div>
          ))}
        </HistoryPanel>
        <HistoryPanel title="Browser uploads">
          {batches.data?.map((batch) => (
            <div className="history-row" key={batch.id}>
              <span>
                <strong>{titleCase(batch.status)}</strong>
                <small>{formatDate(batch.created_at)}</small>
              </span>
              <span className="history-counts">
                {batch.completed_count} imported · {batch.duplicate_count} duplicate ·{" "}
                {batch.failed_count} failed / {batch.total_count} total
              </span>
            </div>
          ))}
        </HistoryPanel>
      </section>
    </main>
  );
}

function HistoryPanel({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  return (
    <article className="panel">
      <p className="kicker">Activity</p>
      <h2>{title}</h2>
      <div className="history-list">{children}</div>
    </article>
  );
}
