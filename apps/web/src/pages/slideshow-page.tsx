import { useQuery } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate, useSearchParams } from "react-router";

import {
  apiRequest,
  type SlideshowItem,
  type SlideshowPlaylist,
} from "../lib/api";
import { slideshowPlaylistQuery } from "../lib/media-view";

const controlsIdleMilliseconds = 2_500;

export function SlideshowPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const playlistSearch = useMemo(
    () => slideshowPlaylistQuery(searchParams).toString(),
    [searchParams],
  );
  const playlist = useQuery({
    queryKey: ["slideshow", playlistSearch],
    queryFn: () =>
      apiRequest<SlideshowPlaylist>(
        `/api/v1/media/slideshow?${playlistSearch}`,
      ),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const [playhead, setPlayhead] = useState(0);
  const [paused, setPaused] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const controlsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const items = playlist.data?.items ?? [];
  const currentIndex = items.length ? playhead % items.length : 0;
  const current = items[currentIndex];
  const next = items.length ? items[(currentIndex + 1) % items.length] : null;
  const intervalMilliseconds = slideshowInterval(searchParams) * 1_000;
  const returnTo = safeReturnPath(searchParams.get("return_to"));

  const advance = useCallback(() => {
    setPlayhead((value) => value + 1);
  }, []);

  const revealControls = useCallback(() => {
    setControlsVisible(true);
    if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    controlsTimerRef.current = setTimeout(
      () => setControlsVisible(false),
      controlsIdleMilliseconds,
    );
  }, []);

  useEffect(() => {
    controlsTimerRef.current = setTimeout(
      () => setControlsVisible(false),
      controlsIdleMilliseconds,
    );
    return () => {
      if (controlsTimerRef.current) clearTimeout(controlsTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (!current || paused) return;
    const timeout = setTimeout(
      advance,
      current.kind === "image"
        ? intervalMilliseconds
        : videoFallbackMilliseconds(current),
    );
    return () => clearTimeout(timeout);
  }, [advance, current, intervalMilliseconds, paused, playhead]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || current?.kind !== "video") return;
    if (paused) {
      video.pause();
      return;
    }
    void video.play().catch(() => {
      // Muted autoplay normally succeeds; the fallback timer still advances if denied.
    });
  }, [current, paused, playhead]);

  useEffect(() => {
    if (next?.kind !== "image") return;
    const image = new Image();
    image.src = next.preview_url;
  }, [next]);

  async function exitSlideshow() {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
    } catch {
      // Navigation remains available when the browser owns fullscreen state.
    }
    navigate(returnTo, { replace: true });
  }

  if (playlist.isPending) {
    return (
      <main className="slideshow-page slideshow-status-page">
        <span className="spinner" />
        <p>Preparing slideshow…</p>
      </main>
    );
  }

  if (playlist.isError) {
    return (
      <main className="slideshow-page slideshow-status-page">
        <strong>The slideshow could not be loaded.</strong>
        <button className="secondary-button" onClick={() => void exitSlideshow()}>
          Return to Library
        </button>
      </main>
    );
  }

  if (!current) {
    return (
      <main className="slideshow-page slideshow-status-page">
        <strong>No media matches this slideshow source.</strong>
        <button className="secondary-button" onClick={() => void exitSlideshow()}>
          Return to Library
        </button>
      </main>
    );
  }

  return (
    <main
      className="slideshow-page"
      data-controls-visible={controlsVisible}
      onPointerMove={revealControls}
      onPointerDown={revealControls}
    >
      <div className="slideshow-stage">
        {current.kind === "video" ? (
          <video
            className="slideshow-media"
            key={`${current.id}-${playhead}`}
            ref={videoRef}
            src={current.playback_url}
            poster={current.preview_url}
            autoPlay
            muted
            playsInline
            preload="auto"
            onEnded={advance}
          />
        ) : (
          <img
            className="slideshow-media"
            key={`${current.id}-${playhead}`}
            src={current.preview_url}
            alt=""
          />
        )}
        {next?.kind === "video" && next.id !== current.id ? (
          <video
            className="slideshow-preload"
            src={next.playback_url}
            muted
            preload="metadata"
            aria-hidden="true"
          />
        ) : null}
      </div>

      <div className="slideshow-topbar" aria-hidden={!controlsVisible}>
        <div>
          <strong>{current.original_filename}</strong>
          <span>
            {currentIndex + 1} / {items.length}
            {playlist.data.truncated
              ? ` · first ${playlist.data.limit} of ${playlist.data.total}`
              : ""}
            {playlist.data.shuffle ? " · shuffled" : ""}
          </span>
        </div>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={() => void exitSlideshow()}
        >
          Exit
        </button>
      </div>

      <div className="slideshow-controls" aria-hidden={!controlsVisible}>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={() => setPaused((value) => !value)}
        >
          {paused ? "Resume" : "Pause"}
        </button>
      </div>
    </main>
  );
}

function slideshowInterval(search: URLSearchParams): number {
  const value = Number(search.get("interval"));
  return [5, 8, 12, 20].includes(value) ? value : 8;
}

function safeReturnPath(value: string | null): string {
  return value?.startsWith("/library") ? value : "/library";
}

function videoFallbackMilliseconds(item: SlideshowItem): number {
  const expectedDuration = (item.duration_seconds ?? 120) * 1_000;
  return Math.max(30_000, expectedDuration + 15_000);
}
