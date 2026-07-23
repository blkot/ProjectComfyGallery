import type { Dispatch, SetStateAction } from "react";

import { ApiClientError, type RegistrySyncRun } from "../lib/api";
import { formatDate, titleCase } from "../lib/format";

export const registryPageSize = 100;

export function RegistrySyncHistory({ runs }: { runs: RegistrySyncRun[] }) {
  if (!runs.length) return null;
  return (
    <details className="panel registry-history">
      <summary>Recent synchronization runs</summary>
      <div className="history-list">
        {runs.slice(0, 8).map((run) => (
          <div className="history-row" key={run.id}>
            <span>
              <strong>{titleCase(run.status)}</strong>
              <small>
                {formatDate(run.created_at)} ·{" "}
                {run.current_stage ? titleCase(run.current_stage) : "Complete"}
              </small>
            </span>
            <span className="history-counts">
              {summarizeCounts(run.counts) ||
                run.error_message ||
                "Awaiting results"}
            </span>
          </div>
        ))}
      </div>
    </details>
  );
}

export function RegistryPagination({
  offset,
  total,
  onChange,
}: {
  offset: number;
  total: number;
  onChange: Dispatch<SetStateAction<number>>;
}) {
  if (total <= registryPageSize) return null;
  return (
    <nav className="pagination" aria-label="Registry pages">
      <button
        className="secondary-button"
        type="button"
        disabled={offset === 0}
        onClick={() => onChange((current) => Math.max(0, current - registryPageSize))}
      >
        Previous
      </button>
      <span>
        {offset + 1}–{Math.min(offset + registryPageSize, total)} of {total}
      </span>
      <button
        className="secondary-button"
        type="button"
        disabled={offset + registryPageSize >= total}
        onClick={() => onChange((current) => current + registryPageSize)}
      >
        Next
      </button>
    </nav>
  );
}

export function RegistryStatusChip({ value }: { value: string }) {
  return (
    <span className="status-chip" data-status={value}>
      {titleCase(value)}
    </span>
  );
}

export function RegistryError({
  error,
  fallback,
}: {
  error: unknown;
  fallback: string;
}) {
  return (
    <p className="notice error-notice" role="alert">
      {error instanceof ApiClientError ? error.message : fallback}
    </p>
  );
}

function summarizeCounts(counts: Record<string, unknown>): string {
  return Object.entries(counts)
    .filter(([, value]) => typeof value === "number")
    .slice(0, 4)
    .map(([key, value]) => `${value} ${key.replaceAll("_", " ")}`)
    .join(" · ");
}
