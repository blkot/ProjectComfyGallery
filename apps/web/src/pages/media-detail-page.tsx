import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { WorkflowInspector } from "../components/workflow-inspector";
import { apiRequest, type MediaDetail } from "../lib/api";
import { formatBytes, formatDate, formatDuration, titleCase } from "../lib/format";

export function MediaDetailPage() {
  const { mediaId = "" } = useParams();
  const media = useQuery({
    queryKey: ["media-detail", mediaId],
    queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${mediaId}`),
    enabled: Boolean(mediaId),
  });

  if (media.isPending) {
    return (
      <main className="page">
        <p className="muted">Loading media record…</p>
      </main>
    );
  }
  if (media.isError || !media.data) {
    return (
      <main className="page">
        <p className="notice error-notice">The media record could not be loaded.</p>
        <Link className="secondary-button link-button" to="/library">
          Back to library
        </Link>
      </main>
    );
  }

  const item = media.data;
  return (
    <main className="page media-detail-page">
      <header className="detail-nav">
        <Link to="/library">← Media library</Link>
        <a className="secondary-button link-button" href={`${item.original_url}?download=true`}>
          Download original
        </a>
      </header>

      <section className="media-detail-layout">
        <div className="detail-viewer">
          {item.kind === "video" ? (
            <video src={item.playback_url} controls preload="metadata" poster={item.preview_url} />
          ) : (
            <img src={item.original_url} alt={item.original_filename} />
          )}
        </div>
        <aside className="detail-sidebar">
          <p className="kicker">{item.kind}</p>
          <h1>{item.original_filename}</h1>
          <span className="status-chip" data-status={item.status}>
            {titleCase(item.status)}
          </span>
          {item.last_error_code ? (
            <div className="notice error-notice">
              <strong>{item.last_error_code}</strong>
              <p>{item.last_error_message}</p>
            </div>
          ) : null}

          <dl className="metadata-list">
            <div>
              <dt>Dimensions</dt>
              <dd>
                {item.width && item.height ? `${item.width} × ${item.height}` : "Unknown"}
              </dd>
            </div>
            <div>
              <dt>Format</dt>
              <dd>{titleCase(item.detected_format ?? item.kind)}</dd>
            </div>
            {item.kind === "video" ? (
              <>
                <div>
                  <dt>Duration</dt>
                  <dd>{formatDuration(item.duration_seconds)}</dd>
                </div>
                <div>
                  <dt>Video codec</dt>
                  <dd>{item.video_codec ?? "Unknown"}</dd>
                </div>
              </>
            ) : null}
            <div>
              <dt>Original size</dt>
              <dd>{formatBytes(item.byte_size)}</dd>
            </div>
            <div>
              <dt>Imported</dt>
              <dd>{formatDate(item.created_at)}</dd>
            </div>
            <div>
              <dt>Workflow evidence</dt>
              <dd>{titleCase(item.workflow_status)}</dd>
            </div>
          </dl>

          <div className="identity-block">
            <span>Media UUID</span>
            <code>{item.id}</code>
            <span>SHA-256 content identity</span>
            <code>{item.sha256}</code>
          </div>
        </aside>
      </section>

      <section className="history-grid section-block">
        <article className="panel">
          <p className="kicker">Derived assets</p>
          <h2>Preview artifacts</h2>
          <div className="history-list">
            {item.derivatives.map((derivative) => (
              <div className="history-row" key={derivative.id}>
                <span>
                  <strong>{titleCase(derivative.kind)}</strong>
                  <small>{derivative.recipe_version}</small>
                </span>
                <span className="history-counts">{formatBytes(derivative.byte_size)}</span>
              </div>
            ))}
          </div>
        </article>
        <article className="panel">
          <p className="kicker">Observed paths</p>
          <h2>Source history</h2>
          <div className="history-list">
            {item.sources.map((source) => (
              <div className="history-row source-history-row" key={source.id}>
                <span>
                  <strong>{source.relative_path}</strong>
                  <small>
                    {titleCase(source.status)} · {formatDate(source.created_at)}
                  </small>
                </span>
              </div>
            ))}
            {item.sources.length === 0 ? (
              <p className="muted">Imported through the browser; no source path recorded.</p>
            ) : null}
          </div>
        </article>
      </section>
      <WorkflowInspector mediaId={item.id} />
    </main>
  );
}
