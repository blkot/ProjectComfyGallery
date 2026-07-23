import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiRequest,
  type PortableExport,
  type SystemStatus,
} from "../lib/api";
import { formatBytes, formatDate } from "../lib/format";

const checkLabels: Record<string, string> = {
  database: "PostgreSQL",
  redis: "Redis broker",
  worker: "Background worker",
  jobs: "Durable jobs",
  managed_storage: "Managed media storage",
  staging_storage: "Upload staging",
  export_storage: "Portable export storage",
  database_backup: "Database backup",
  recent_activity: "Recent activity",
};

function statusLabel(status: string) {
  if (status === "ok") return "Healthy";
  if (status === "warning") return "Warning";
  return "Needs attention";
}

export function OperationsPage() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiRequest<SystemStatus>("/api/v1/system/status"),
    refetchInterval: 15_000,
  });
  const exports = useQuery({
    queryKey: ["portable-exports"],
    queryFn: () => apiRequest<PortableExport[]>("/api/v1/exports?limit=50"),
    refetchInterval: (query) =>
      query.state.data?.some((item) => ["queued", "running"].includes(item.status))
        ? 3_000
        : 30_000,
  });
  const createExport = useMutation({
    mutationFn: () =>
      apiRequest<PortableExport>("/api/v1/exports", {
        method: "POST",
        body: JSON.stringify({ include_workflow_evidence: true }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["portable-exports"] });
      await queryClient.invalidateQueries({ queryKey: ["system-status"] });
    },
  });

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <p className="kicker">Operations · Phase 6</p>
          <h1>NAS health and recovery</h1>
          <p className="muted">
            Worker freshness, durable queues, disk pressure, database backups, and
            secret-free portable exports in one place.
          </p>
        </div>
        <div
          className="health-pill"
          data-state={status.data?.status === "ok" ? "ok" : "wait"}
        >
          <span />
          {status.isPending
            ? "Checking"
            : status.data?.status === "ok"
              ? "All checks healthy"
              : "Review warnings"}
        </div>
      </header>

      {status.data?.warnings.length ? (
        <div className="notice error-notice" role="status">
          <strong>Operational warnings</strong>
          <ul className="compact-list">
            {status.data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <section className="operations-grid" aria-label="Operational checks">
        {Object.entries(status.data?.checks ?? {}).map(([key, check]) => {
          const usedPercent = check.data.used_percent;
          const freeBytes = check.data.free_bytes;
          const ageHours = check.data.age_hours;
          return (
            <article className="operation-card" data-state={check.status} key={key}>
              <div className="operation-card-heading">
                <h2>{checkLabels[key] ?? key}</h2>
                <span>{statusLabel(check.status)}</span>
              </div>
              <p>{check.detail ?? "No issues reported."}</p>
              {typeof usedPercent === "number" ? (
                <small>
                  {usedPercent.toFixed(1)}% used ·{" "}
                  {typeof freeBytes === "number" ? formatBytes(freeBytes) : "—"} free
                </small>
              ) : null}
              {typeof ageHours === "number" ? (
                <small>Latest successful backup: {ageHours.toFixed(1)} hours ago</small>
              ) : null}
            </article>
          );
        })}
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="kicker">Portability</p>
            <h2>User-data exports</h2>
            <p className="muted">
              JSON Lines preserve stable IDs and history; CSV summaries make scores and
              analysis results easy to inspect. Passwords, sessions, and tokens are
              excluded.
            </p>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={createExport.isPending}
            onClick={() => createExport.mutate()}
          >
            {createExport.isPending ? "Queueing…" : "Create portable export"}
          </button>
        </div>

        {createExport.isError ? (
          <div className="notice error-notice" role="alert">
            The export could not be queued. Check the worker and broker status.
          </div>
        ) : null}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Created</th>
                <th>Status</th>
                <th>Size</th>
                <th>Integrity</th>
                <th>Bundle</th>
              </tr>
            </thead>
            <tbody>
              {(exports.data ?? []).map((item) => (
                <tr key={item.id}>
                  <td>{formatDate(item.created_at)}</td>
                  <td>
                    <span className="status-chip" data-state={item.status}>
                      {item.status}
                    </span>
                    {item.error_message ? <small>{item.error_message}</small> : null}
                  </td>
                  <td>{item.byte_size ? formatBytes(item.byte_size) : "—"}</td>
                  <td className="mono-cell">
                    {item.sha256 ? `${item.sha256.slice(0, 12)}…` : "—"}
                  </td>
                  <td>
                    {item.download_url ? (
                      <a className="text-link" href={item.download_url}>
                        Download ZIP
                      </a>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
              {!exports.isPending && !exports.data?.length ? (
                <tr>
                  <td colSpan={5}>No portable exports have been created.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
