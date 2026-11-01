import { useInfiniteQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";

import { apiRequest, type MediaPage } from "../lib/api";
import { buildPhotoWallRows } from "../lib/photo-wall";
import {
  mediaDetailHref,
  mediaPageSize,
  photoWallQuery,
} from "../lib/media-view";

const defaultImageWidth = 190;
const minimumZoom = 0.5;
const maximumZoom = 2;
const zoomStep = 0.1;

export function PhotoWallPage() {
  const [searchParams] = useSearchParams();
  const wallRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(readViewportWidth);
  const [zoom, setZoom] = useState(1);
  const loadingMoreRef = useRef(false);
  const wallSearch = useMemo(
    () => photoWallQuery(searchParams).toString(),
    [searchParams],
  );
  const detailSearch = useMemo(
    () => photoWallQuery(searchParams),
    [searchParams],
  );
  const returnTo = safeLibraryPath(searchParams.get("return_to"));
  const wall = useInfiniteQuery({
    queryKey: ["photo-wall", wallSearch],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      const requestSearch = new URLSearchParams(wallSearch);
      requestSearch.set("limit", String(mediaPageSize));
      requestSearch.set("offset", String(pageParam));
      return apiRequest<MediaPage>(`/api/v1/media?${requestSearch}`);
    },
    getNextPageParam: (lastPage) => {
      const nextOffset = lastPage.offset + lastPage.items.length;
      return lastPage.items.length > 0 && nextOffset < lastPage.total
        ? nextOffset
        : undefined;
    },
    staleTime: 30_000,
  });
  const items = useMemo(
    () => wall.data?.pages.flatMap((page) => page.items) ?? [],
    [wall.data],
  );
  const total = wall.data?.pages[0]?.total ?? 0;
  const imageWidth = defaultImageWidth * zoom;
  const rows = useMemo(
    () => buildPhotoWallRows(items, containerWidth, imageWidth),
    [containerWidth, imageWidth, items],
  );
  const eagerItemIds = useMemo(
    () => new Set(items.slice(0, 16).map((item) => item.id)),
    [items],
  );
  const {
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = wall;
  const loadMore = useCallback(() => {
    if (!hasNextPage || isFetchingNextPage || loadingMoreRef.current) return;
    loadingMoreRef.current = true;
    void fetchNextPage().finally(() => {
      loadingMoreRef.current = false;
    });
  }, [fetchNextPage, hasNextPage, isFetchingNextPage]);

  useEffect(() => {
    const element = wallRef.current;
    if (!element) return;

    const measure = () => {
      setContainerWidth(element.clientWidth || readViewportWidth());
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }

    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const element = loadMoreRef.current;
    if (!element || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) loadMore();
      },
      { rootMargin: "720px 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [loadMore]);

  useEffect(() => {
    if (!hasNextPage || isFetchingNextPage) return;

    const maybeLoadMore = () => {
      const distanceToBottom =
        document.documentElement.scrollHeight -
        (window.scrollY + window.innerHeight);
      if (distanceToBottom < 720) loadMore();
    };
    window.addEventListener("scroll", maybeLoadMore, { passive: true });
    window.addEventListener("wheel", maybeLoadMore, { passive: true });
    return () => {
      window.removeEventListener("scroll", maybeLoadMore);
      window.removeEventListener("wheel", maybeLoadMore);
    };
  }, [hasNextPage, isFetchingNextPage, loadMore]);

  return (
    <main className="photo-wall-page">
      <header className="photo-wall-header">
        <div className="photo-wall-heading">
          <Link className="photo-wall-back" to={returnTo}>
            ← Library
          </Link>
          <div>
            <p className="kicker">Gapless image preview</p>
            <h1>Photo wall</h1>
            <p className="muted">
              {total
                ? `${total} images in the current filter`
                : "Current image filter"}
            </p>
          </div>
        </div>
        <div className="photo-wall-actions">
          <label className="photo-wall-zoom">
            <span>Zoom</span>
            <input
              aria-label="Photo wall zoom"
              max={maximumZoom}
              min={minimumZoom}
              onChange={(event) => setZoom(Number(event.target.value))}
              step={zoomStep}
              type="range"
              value={zoom}
            />
            <output>{zoom.toFixed(1)}×</output>
          </label>
          <span className="photo-wall-count" aria-live="polite">
            {items.length} / {total || "—"} loaded
          </span>
        </div>
      </header>

      {wall.isError ? (
        <section className="photo-wall-status" role="alert">
          <strong>The photo wall could not be loaded.</strong>
          <Link className="secondary-button link-button" to={returnTo}>
            Return to library
          </Link>
        </section>
      ) : wall.isPending ? (
        <section className="photo-wall-status" aria-live="polite">
          <span className="spinner" />
          <p>Loading filtered images…</p>
        </section>
      ) : items.length === 0 ? (
        <section className="photo-wall-status">
          <strong>No images match this filter.</strong>
          <Link className="secondary-button link-button" to={returnTo}>
            Return to library
          </Link>
        </section>
      ) : (
        <>
          <section
            ref={wallRef}
            className="photo-wall-grid"
            aria-busy={isFetchingNextPage}
            aria-label="Filtered image photo wall"
          >
            {rows.map((row, rowIndex) => (
              <div
                className="photo-wall-row"
                key={`${row.items[0]?.item.id ?? "row"}-${rowIndex}`}
                style={{ minHeight: `${row.height}px` }}
              >
                {row.items.map(({ item, width, height }) => (
                  <Link
                    className="photo-wall-item"
                    key={item.id}
                    style={{ height: `${height}px`, width: `${width}px` }}
                    to={mediaDetailHref(item.id, detailSearch)}
                    title={item.original_filename}
                  >
                    {item.status === "ready" ||
                    item.status === "ready_with_warnings" ? (
                      <img
                        alt={item.original_filename}
                        decoding="async"
                        height={height}
                        loading={eagerItemIds.has(item.id) ? "eager" : "lazy"}
                        src={item.preview_url}
                        width={width}
                      />
                    ) : (
                      <span className="photo-wall-placeholder">
                        {item.original_filename}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            ))}
          </section>
          <div ref={loadMoreRef} className="photo-wall-load-more">
            {hasNextPage ? (
              <>
                <button
                  className="secondary-button"
                  disabled={isFetchingNextPage}
                  onClick={loadMore}
                  type="button"
                >
                  {isFetchingNextPage ? "Loading more…" : "Load more images"}
                </button>
                <small>Scroll or use the wheel to load the next batch.</small>
              </>
            ) : (
              <small>End of the current filter · {items.length} images</small>
            )}
          </div>
        </>
      )}
    </main>
  );
}

function readViewportWidth(): number {
  return typeof window === "undefined" ? 1280 : Math.max(window.innerWidth, 1);
}

function safeLibraryPath(value: string | null): string {
  return value?.startsWith("/library") ? value : "/library";
}
