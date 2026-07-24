import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import {
  apiRequest,
  type Collection,
  type ReviewSession,
  type ReviewSummary,
  type SavedFilter,
  type SourceRoot,
} from "../lib/api";
import { titleCase } from "../lib/format";

type StartSource =
  | "random"
  | "in_progress"
  | "collection"
  | "saved_filter"
  | "source";

export function ReviewHomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sourceKind, setSourceKind] = useState<StartSource>("random");
  const [sourceId, setSourceId] = useState("");
  const [limit, setLimit] = useState("100");
  const [randomize, setRandomize] = useState(true);
  const [character, setCharacter] = useState(false);

  const summary = useQuery({
    queryKey: ["review-summary"],
    queryFn: () => apiRequest<ReviewSummary>("/api/v1/review/summary"),
  });
  const sessions = useQuery({
    queryKey: ["review-sessions"],
    queryFn: () => apiRequest<ReviewSession[]>("/api/v1/review-sessions"),
  });
  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: () => apiRequest<Collection[]>("/api/v1/collections"),
  });
  const filters = useQuery({
    queryKey: ["saved-filters"],
    queryFn: () => apiRequest<SavedFilter[]>("/api/v1/saved-filters"),
  });
  const roots = useQuery({
    queryKey: ["source-roots"],
    queryFn: () => apiRequest<SourceRoot[]>("/api/v1/source-roots"),
  });
  const start = useMutation({
    mutationFn: () =>
      apiRequest<ReviewSession>("/api/v1/review-sessions", {
        method: "POST",
        body: JSON.stringify({
          source_kind: sourceKind,
          collection_id: sourceKind === "collection" ? sourceId : null,
          saved_filter_id: sourceKind === "saved_filter" ? sourceId : null,
          source_root_id: sourceKind === "source" ? sourceId : null,
          filter:
            sourceKind === "random"
              ? { evaluation_state: "not_started", trash: false }
              : null,
          random_limit: Number(limit),
          ordering_mode: randomize ? "random" : "stable",
          optional_modules: character ? ["character"] : [],
        }),
      }),
    onSuccess: async (reviewSession) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["review-sessions"] }),
      ]);
      navigate(`/review/${reviewSession.id}`);
    },
  });

  const needsSource = ["collection", "saved_filter", "source"].includes(sourceKind);
  const sourceOptions =
    sourceKind === "collection"
      ? collections.data?.map((item) => ({ id: item.id, label: item.name }))
      : sourceKind === "saved_filter"
        ? filters.data?.map((item) => ({ id: item.id, label: item.name }))
        : sourceKind === "source"
          ? roots.data?.map((item) => ({ id: item.id, label: item.name }))
          : [];

  return (
    <main className="page review-home-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Configuration-blind scoring · Phase 4</p>
          <h1>Blind review</h1>
          <p className="muted">
            Work a little or a lot. Every decision saves independently and no score,
            completion, or Trash action moves you forward automatically.
          </p>
        </div>
      </header>

      <section className="review-summary-grid" aria-label="Evaluation status">
        <SummaryCard
          label="Not started"
          value={summary.data?.not_started_count}
          tone="neutral"
        />
        <SummaryCard
          label="In progress"
          value={summary.data?.in_progress_count}
          tone="wait"
        />
        <SummaryCard
          label="Complete"
          value={summary.data?.complete_count}
          tone="ok"
        />
        <SummaryCard label="Trash" value={summary.data?.trash_count} tone="danger" />
      </section>

      <section className="review-home-grid">
        <form
          className="panel review-start-panel"
          onSubmit={(event) => {
            event.preventDefault();
            start.mutate();
          }}
        >
          <p className="kicker">New session</p>
          <h2>Choose a review pool</h2>
          <label>
            Start from
            <select
              value={sourceKind}
              onChange={(event) => {
                setSourceKind(event.target.value as StartSource);
                setSourceId("");
              }}
            >
              <option value="random">Random unevaluated media</option>
              <option value="in_progress">Global In progress pool</option>
              <option value="collection">Collection</option>
              <option value="saved_filter">Saved filter</option>
              <option value="source">Source directory</option>
            </select>
          </label>
          {needsSource ? (
            <label>
              Scope
              <select
                required
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
              >
                <option value="">Choose a scope</option>
                {sourceOptions?.map((option) => (
                  <option value={option.id} key={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Maximum media
            <input
              type="number"
              min="1"
              max="2000"
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
            />
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={randomize}
              onChange={(event) => setRandomize(event.target.checked)}
            />
            Randomize stable session order
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={character}
              onChange={(event) => setCharacter(event.target.checked)}
            />
            Add character identity module
          </label>
          {start.error ? (
            <p className="notice error-notice" role="alert">
              {start.error.message}
            </p>
          ) : null}
          <button
            className="primary-button"
            type="submit"
            disabled={start.isPending || (needsSource && !sourceId)}
          >
            {start.isPending ? "Preparing session…" : "Start review"}
          </button>
        </form>

        <section className="panel recent-review-panel">
          <div className="section-heading">
            <div>
              <p className="kicker">Resume without pressure</p>
              <h2>Recent sessions</h2>
            </div>
            <span className="document-count">
              {summary.data?.active_session_count ?? "—"} active
            </span>
          </div>
          <div className="review-session-list">
            {sessions.data?.map((reviewSession) => (
              <Link
                className="review-session-card"
                to={`/review/${reviewSession.id}`}
                key={reviewSession.id}
              >
                <span>
                  <strong>
                    {reviewSession.name ||
                      `${titleCase(reviewSession.source_kind)} review`}
                  </strong>
                  <small>
                    Position {reviewSession.current_cursor + 1} of{" "}
                    {reviewSession.candidate_count}
                  </small>
                </span>
                <span>
                  <strong>
                    {reviewSession.progress_counts.complete ?? 0} complete
                  </strong>
                  <small>{titleCase(reviewSession.status)}</small>
                </span>
              </Link>
            ))}
            {sessions.data?.length === 0 ? (
              <div className="empty-state">
                <strong>No review sessions yet</strong>
                <p>Start with random media or prepare a scope in the library.</p>
              </div>
            ) : null}
          </div>
        </section>
      </section>
    </main>
  );
}

function SummaryCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | undefined;
  tone: string;
}) {
  return (
    <article className="summary-card review-summary-card" data-tone={tone}>
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </article>
  );
}
