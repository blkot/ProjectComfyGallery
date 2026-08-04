import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router";

import { MediaFavoriteButton } from "../components/media-favorite-button";
import { MediaEvaluationPanel } from "../components/media-evaluation-panel";
import { MediaSpatialPreferenceButton } from "../components/media-spatial-preference-button";
import { MediaTrashButton } from "../components/media-trash-button";
import { SpatialVariantAttachment } from "../components/spatial-variant-attachment";
import { WorkflowInspector } from "../components/workflow-inspector";
import {
  apiRequest,
  type MediaDetail,
  type MediaNavigation,
} from "../lib/api";
import { formatBytes, formatDate, formatDuration, titleCase } from "../lib/format";
import {
  mediaDetailHref,
  mediaLibraryHref,
  mediaNavigationQuery,
} from "../lib/media-view";

export function MediaDetailPage() {
  const { mediaId = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const activePanel =
    searchParams.get("panel") === "evaluation" ? "evaluation" : "information";
  const navigationSearch = mediaNavigationQuery(searchParams).toString();
  const libraryHref = mediaLibraryHref(searchParams);
  const media = useQuery({
    queryKey: ["media-detail", mediaId],
    queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${mediaId}`),
    enabled: Boolean(mediaId),
  });
  const navigation = useQuery({
    queryKey: ["media-navigation", mediaId, navigationSearch],
    queryFn: () =>
      apiRequest<MediaNavigation>(
        `/api/v1/media/${mediaId}/navigation?${navigationSearch}`,
      ),
    enabled: Boolean(mediaId),
  });
  const previousHref = navigation.data?.previous_id
    ? mediaDetailHref(
        navigation.data.previous_id,
        searchParams,
        navigation.data.previous_position,
      )
    : null;
  const nextHref = navigation.data?.next_id
    ? mediaDetailHref(
        navigation.data.next_id,
        searchParams,
        navigation.data.next_position,
      )
    : null;

  useEffect(() => {
    if (!mediaId) return;
    void queryClient.prefetchQuery({
      queryKey: ["media-workflow", mediaId],
      queryFn: () =>
        apiRequest(
          `/api/v1/media/${mediaId}/workflow?node_limit=1000&edge_limit=3000`,
        ),
    });
  }, [mediaId, queryClient]);

  useEffect(() => {
    function handleKeyboardNavigation(event: KeyboardEvent) {
      const target = event.target;
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
        return;
      }
      if (
        target instanceof HTMLElement &&
        (target.isContentEditable ||
          ["AUDIO", "INPUT", "SELECT", "TEXTAREA", "VIDEO"].includes(
            target.tagName,
          ))
      ) {
        return;
      }
      if (event.key === "ArrowLeft" && previousHref) {
        event.preventDefault();
        navigate(previousHref);
      } else if (event.key === "ArrowRight" && nextHref) {
        event.preventDefault();
        navigate(nextHref);
      }
    }
    window.addEventListener("keydown", handleKeyboardNavigation);
    return () => window.removeEventListener("keydown", handleKeyboardNavigation);
  }, [navigate, nextHref, previousHref]);

  function prefetchMedia(targetId: string | null) {
    if (!targetId) return;
    void queryClient.prefetchQuery({
      queryKey: ["media-detail", targetId],
      queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${targetId}`),
    });
  }

  function selectPanel(panel: "information" | "evaluation") {
    const next = new URLSearchParams(searchParams);
    if (panel === "information") {
      next.delete("panel");
    } else {
      next.set("panel", panel);
    }
    setSearchParams(next, { replace: true });
  }

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
        <Link className="secondary-button link-button" to={libraryHref}>
          Back to library
        </Link>
      </main>
    );
  }

  const item = media.data;
  return (
    <main className="media-record-workspace">
      <section className="media-record-preview" aria-label="Media preview">
        <header className="media-record-toolbar">
          <Link className="media-record-back" to={libraryHref}>
            ← Library
          </Link>
          <nav
            className="media-view-navigation"
            aria-label="Media viewer navigation"
          >
            <button
              type="button"
              disabled={!previousHref}
              aria-label="Previous media"
              aria-keyshortcuts="ArrowLeft"
              onClick={() => {
                if (previousHref) navigate(previousHref);
              }}
              onFocus={() =>
                prefetchMedia(navigation.data?.previous_id ?? null)
              }
              onMouseEnter={() =>
                prefetchMedia(navigation.data?.previous_id ?? null)
              }
            >
              ←
            </button>
            <span aria-live="polite">
              {navigation.data
                ? `${navigation.data.position} / ${navigation.data.total}`
                : navigation.isError
                  ? "Outside view"
                  : "Locating…"}
            </span>
            <button
              type="button"
              disabled={!nextHref}
              aria-label="Next media"
              aria-keyshortcuts="ArrowRight"
              onClick={() => {
                if (nextHref) navigate(nextHref);
              }}
              onFocus={() => prefetchMedia(navigation.data?.next_id ?? null)}
              onMouseEnter={() =>
                prefetchMedia(navigation.data?.next_id ?? null)
              }
            >
              →
            </button>
          </nav>
          <div
            className="media-record-actions"
            role="group"
            aria-label="Media actions"
          >
            <MediaFavoriteButton
              mediaId={item.id}
              favorite={item.favorite}
              className="media-record-favorite"
            />
            <MediaSpatialPreferenceButton
              mediaId={item.id}
              preferred={item.prefer_spatial_playback}
              className="media-record-spatial"
            />
            <a
              className="media-record-download"
              href={`${item.original_url}?download=true`}
            >
              Download
            </a>
            <MediaTrashButton mediaId={item.id} isTrash={item.is_trash} />
          </div>
        </header>
        <div className="media-record-stage">
          {item.kind === "video" ? (
            <video
              src={item.playback_url}
              controls
              playsInline
              preload="metadata"
              poster={item.preview_url}
            />
          ) : (
            <img src={item.original_url} alt={item.original_filename} />
          )}
        </div>
      </section>

      <aside className="media-record-inspector">
        <header className="media-record-heading">
          <p className="kicker">{item.kind}</p>
          <div className="media-record-title-row">
            <h1>{item.original_filename}</h1>
            <div
              className="media-record-panel-switcher"
              role="tablist"
              aria-label="Media record panel"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activePanel === "information"}
                onClick={() => selectPanel("information")}
              >
                Info
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={activePanel === "evaluation"}
                onClick={() => selectPanel("evaluation")}
              >
                Evaluate
              </button>
            </div>
          </div>
          <div className="media-record-statuses">
            <span className="status-chip" data-status={item.status}>
              {titleCase(item.status)}
            </span>
            <span className="status-chip" data-status={item.workflow_status}>
              Workflow {titleCase(item.workflow_status)}
            </span>
            {item.kind === "video" ? (
              <span
                className="status-chip"
                data-status={item.spatial_available ? "spatial-ready" : "neutral"}
              >
                {item.spatial_available
                  ? "Spatial variant ready"
                  : "No spatial video variant"}
              </span>
            ) : null}
          </div>
        </header>

        <div
          className="media-record-panel"
          role="tabpanel"
          aria-label={
            activePanel === "information"
              ? "Media information"
              : "Media evaluation"
          }
        >
          {activePanel === "information" ? (
            <>
            {item.last_error_code ? (
              <div className="notice error-notice">
                <strong>{item.last_error_code}</strong>
                <p>{item.last_error_message}</p>
              </div>
            ) : null}

            {item.kind === "video" ? (
              <SpatialVariantAttachment media={item} />
            ) : null}

            <WorkflowInspector mediaId={item.id} />

            <details className="record-inspector-disclosure">
              <summary>
                <span>
                  <strong>Storage &amp; derivatives</strong>
                  <small>Source paths and generated previews</small>
                </span>
                <span>
                  {item.sources.length} paths ·{" "}
                  {item.derivatives.length + item.variants.length} assets
                </span>
              </summary>
              <div className="record-inspector-disclosure-body">
                <section>
                  <h3>Source history</h3>
                  <div className="history-list">
                    {item.sources.map((source) => (
                      <div
                        className="history-row source-history-row"
                        key={source.id}
                      >
                        <span>
                          <strong>{source.relative_path}</strong>
                          <small>
                            {titleCase(source.status)} ·{" "}
                            {formatDate(source.created_at)}
                          </small>
                        </span>
                      </div>
                    ))}
                    {item.sources.length === 0 ? (
                      <p className="muted">
                        Imported through the browser; no source path recorded.
                      </p>
                    ) : null}
                  </div>
                </section>
                <section>
                  <h3>Derived assets</h3>
                  <div className="history-list">
                    {item.derivatives.map((derivative) => (
                      <div className="history-row" key={derivative.id}>
                        <span>
                          <strong>{titleCase(derivative.kind)}</strong>
                          <small>{derivative.recipe_version}</small>
                        </span>
                        <span className="history-counts">
                          {formatBytes(derivative.byte_size)}
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
                {item.kind === "video" ? (
                  <section>
                    <h3>Spatial video</h3>
                    <div className="history-list">
                      {item.variants.map((variant) => (
                        <div className="history-row" key={variant.id}>
                          <span>
                            <strong>Active spatial variant</strong>
                            <small>
                              {titleCase(variant.video_codec ?? "HEVC")} ·{" "}
                              {variant.width && variant.height
                                ? `${variant.width} × ${variant.height}`
                                : "Unknown dimensions"}
                            </small>
                            <small>
                              {variant.converter_name ?? "External converter"}
                              {variant.converter_version
                                ? ` ${variant.converter_version}`
                                : ""}
                            </small>
                          </span>
                          <span className="history-counts">
                            {formatBytes(variant.byte_size)}
                          </span>
                        </div>
                      ))}
                      {item.variants.length === 0 ? (
                        <p className="muted">
                          No active spatial-video variant. Web playback continues
                          to use the ordinary original or browser proxy.
                        </p>
                      ) : (
                        <p className="muted">
                          Stored for spatial clients. This web preview deliberately
                          keeps using the ordinary playback path.
                        </p>
                      )}
                    </div>
                  </section>
                ) : null}
              </div>
            </details>

            <details className="record-inspector-disclosure technical-identity">
              <summary>
                <span>
                  <strong>Technical identity</strong>
                  <small>IDs for troubleshooting and exact deduplication</small>
                </span>
              </summary>
              <dl className="metadata-list">
                <div>
                  <dt>Imported into gallery</dt>
                  <dd>{formatDate(item.created_at)}</dd>
                </div>
                <div>
                  <dt>Video codec</dt>
                  <dd>{item.video_codec ?? "Not applicable"}</dd>
                </div>
              </dl>
              <div className="identity-block">
                <span>Media UUID</span>
                <code>{item.id}</code>
                <span>SHA-256 content identity</span>
                <code>{item.sha256}</code>
              </div>
            </details>

            <section
              className="media-file-details"
              aria-labelledby="media-file-details-title"
            >
              <h2 id="media-file-details-title">File details</h2>
              <dl className="record-facts" aria-label="Basic media metadata">
                <div>
                  <dt>Dimensions</dt>
                  <dd>
                    {item.width && item.height
                      ? `${item.width} × ${item.height}`
                      : "Unknown"}
                  </dd>
                </div>
                <div>
                  <dt>Format</dt>
                  <dd>{titleCase(item.detected_format ?? item.kind)}</dd>
                </div>
                {item.kind === "video" ? (
                  <div>
                    <dt>Duration</dt>
                    <dd>{formatDuration(item.duration_seconds)}</dd>
                  </div>
                ) : null}
                <div>
                  <dt>File size</dt>
                  <dd>{formatBytes(item.byte_size)}</dd>
                </div>
                <div>
                  <dt>File created</dt>
                  <dd>{formatDate(item.file_created_at)}</dd>
                </div>
              </dl>
            </section>
            </>
          ) : (
            <MediaEvaluationPanel mediaId={item.id} key={item.id} />
          )}
        </div>
      </aside>
    </main>
  );
}
