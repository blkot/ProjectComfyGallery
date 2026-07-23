import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiClientError, apiRequest, type Job } from "../lib/api";
import { formatDate, titleCase } from "../lib/format";

export function JobsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const jobs = useQuery({
    queryKey: ["jobs", status],
    queryFn: () =>
      apiRequest<Job[]>(
        `/api/v1/jobs?limit=200${status ? `&job_status=${encodeURIComponent(status)}` : ""}`,
      ),
    refetchInterval: 2_500,
  });
  const retry = useMutation({
    mutationFn: (id: string) =>
      apiRequest<Job>(`/api/v1/jobs/${id}/retry`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const cancel = useMutation({
    mutationFn: (id: string) =>
      apiRequest<Job>(`/api/v1/jobs/${id}/cancel`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["jobs"] }),
  });
  const actionError = retry.error ?? cancel.error;

  return (
    <main className="page jobs-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Durable processing</p>
          <h1>Jobs</h1>
          <p className="muted">
            Each job keeps its current stage, attempt count, progress, and stable error
            code so failed work can be understood and safely retried.
          </p>
        </div>
      </header>

      <section className="toolbar">
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">All jobs</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="failed">Failed</option>
            <option value="succeeded">Succeeded</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </label>
        <span className="result-count">{jobs.data?.length ?? 0} shown</span>
      </section>

      {actionError ? (
        <p className="notice error-notice" role="alert">
          {actionError instanceof ApiClientError
            ? actionError.message
            : "The job action failed."}
        </p>
      ) : null}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Stage / progress</th>
              <th>Created</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {jobs.data?.map((job) => (
              <tr key={job.id}>
                <td>
                  <strong>{titleCase(job.kind)}</strong>
                  <small>
                    {job.queue} · attempt {job.attempt_count}
                  </small>
                </td>
                <td>
                  <span className="status-chip" data-status={job.status}>
                    {titleCase(job.status)}
                  </span>
                  {job.error_code ? (
                    <small className="job-error" title={job.error_message ?? ""}>
                      {job.error_code}
                    </small>
                  ) : null}
                </td>
                <td>
                  <strong>{titleCase(job.stage ?? "Waiting")}</strong>
                  <small>
                    {job.progress_total
                      ? `${job.progress_current} / ${job.progress_total}`
                      : "No measured total"}
                  </small>
                </td>
                <td>
                  <span>{formatDate(job.created_at)}</span>
                </td>
                <td className="job-actions">
                  {job.status === "failed" ? (
                    <button
                      className="secondary-button"
                      type="button"
                      disabled={retry.isPending}
                      onClick={() => retry.mutate(job.id)}
                    >
                      Retry
                    </button>
                  ) : null}
                  {["queued", "running"].includes(job.status) ? (
                    <button
                      className="danger-button"
                      type="button"
                      disabled={cancel.isPending || job.cancel_requested}
                      onClick={() => cancel.mutate(job.id)}
                    >
                      {job.cancel_requested ? "Stopping…" : "Cancel"}
                    </button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.data?.length === 0 ? (
          <div className="empty-state">
            <strong>No jobs match this status</strong>
          </div>
        ) : null}
      </div>
    </main>
  );
}
