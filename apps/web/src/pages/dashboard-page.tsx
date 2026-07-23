import { useQuery } from "@tanstack/react-query";

import {
  apiRequest,
  type Job,
  type MediaPage,
  type ReviewSummary,
  type SystemStatus,
} from "../lib/api";

const foundationItems = [
  {
    title: "Immutable workflow evidence",
    body: "Exact decoded prompt, workflow, and carrier metadata remain the ground truth.",
    status: "Active",
  },
  {
    title: "Unknown-safe graph",
    body: "Every node, edge, named input, and widget remains visible without a registry match.",
    status: "Active",
  },
  {
    title: "Versioned interpretation",
    body: "New extraction runs add observations without overwriting evidence or history.",
    status: "Active",
  },
  {
    title: "Blind, resumable evaluation",
    body: "Nullable 0–10 scores, revision history, and reversible Trash remain independent of navigation.",
    status: "Active",
  },
];

export function DashboardPage() {
  const status = useQuery({
    queryKey: ["system-status"],
    queryFn: () => apiRequest<SystemStatus>("/api/v1/system/status"),
    refetchInterval: 60_000,
  });
  const media = useQuery({
    queryKey: ["dashboard-media-count"],
    queryFn: () => apiRequest<MediaPage>("/api/v1/media?limit=1"),
    refetchInterval: 30_000,
  });
  const jobs = useQuery({
    queryKey: ["dashboard-active-jobs"],
    queryFn: () => apiRequest<Job[]>("/api/v1/jobs?limit=200"),
    refetchInterval: 10_000,
  });
  const review = useQuery({
    queryKey: ["review-summary"],
    queryFn: () => apiRequest<ReviewSummary>("/api/v1/review/summary"),
    refetchInterval: 30_000,
  });
  const activeJobs =
    jobs.data?.filter((job) => ["queued", "running"].includes(job.status)).length ?? 0;

  return (
    <main className="page">
      <header className="page-header">
        <div>
          <p className="kicker">NAS release · Phase 6</p>
          <h1>System overview</h1>
          <p className="muted">
            Preserve workflow evidence, organize the media library, and review outputs
            without exposing checkpoint, LoRA, or workflow variables.
          </p>
        </div>
        <div
          className="health-pill"
          data-state={status.data?.status === "ok" ? "ok" : "wait"}
        >
          <span />
          {status.isPending
            ? "Checking services"
            : status.isSuccess
              ? status.data.status === "ok"
                ? "System healthy"
                : "Needs attention"
              : "Needs attention"}
        </div>
      </header>

      <section className="metric-grid" aria-label="Service status">
        <article className="metric-card featured">
          <p>Managed media</p>
          <strong>{media.data?.total ?? "—"}</strong>
          <small>Unique SHA-256 identities</small>
        </article>
        <article className="metric-card">
          <p>Fully reviewed</p>
          <strong>{review.data?.complete_count ?? "—"}</strong>
          <small>{review.data?.in_progress_count ?? "—"} currently in progress</small>
        </article>
        <article className="metric-card">
          <p>Active jobs</p>
          <strong>{activeJobs}</strong>
          <small>Queued or running</small>
        </article>
        <article className="metric-card">
          <p>Storage pipeline</p>
          <strong>{status.data?.checks.worker?.status ?? "Checking"}</strong>
          <small>PostgreSQL · Redis · worker</small>
        </article>
      </section>

      {status.isError ? (
        <div className="notice error-notice" role="alert">
          One or more foundation services did not respond. Check the API and
          worker logs before importing media.
        </div>
      ) : null}

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="kicker">Product contract</p>
            <h2>What the evidence and review pipeline protects</h2>
          </div>
          <span className="document-count">118 traced requirements</span>
        </div>
        <div className="principle-grid">
          {foundationItems.map((item, index) => (
            <article className="principle-card" key={item.title}>
              <span className="item-number">0{index + 1}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
              <small>{item.status}</small>
            </article>
          ))}
        </div>
      </section>

      <section className="next-step-card">
        <div>
          <p className="kicker">Release posture</p>
          <h2>Recovery and portable data are operational</h2>
          <p>
            Scheduled PostgreSQL backups protect manual work, while secret-free
            JSON/CSV bundles keep evaluation and analysis data portable.
          </p>
        </div>
        <div className="phase-marker">
          <span>06</span>
          <small>Phase</small>
        </div>
      </section>
    </main>
  );
}
