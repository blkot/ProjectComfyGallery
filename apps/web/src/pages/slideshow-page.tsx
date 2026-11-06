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
import { browseScope, safeBrowseHref } from "../lib/media-browse";

const controlsIdleMilliseconds = 2_500;

export function SlideshowPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const promptScope = searchParams.get("source") === "prompt";
  const playlistSearch = useMemo(
    () => {
      if (!promptScope) return slideshowPlaylistQuery(searchParams).toString();
      const params = browseScope("prompt", searchParams);
      params.set("limit", "2000");
      const startId = searchParams.get("start_media");
      if (startId) params.set("start_media_id", startId);
      return params.toString();
    },
    [searchParams, promptScope],
  );
  const playlist = useQuery({
    queryKey: ["slideshow", promptScope ? "prompt" : "library", playlistSearch],
    queryFn: () =>
      apiRequest<SlideshowPlaylist>(
        `${promptScope ? "/api/v1/prompt-registry/usage/slideshow" : "/api/v1/media/slideshow"}?${playlistSearch}`,
      ),
    staleTime: Number.POSITIVE_INFINITY,
  });
  const [playhead, setPlayhead] = useState(0);
  const [paused, setPaused] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const controlsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const items = playlist.data?.items ?? [];
  const startMediaId = searchParams.get("start_media");
  const requestedStartIndex = startMediaId
    ? items.findIndex((item) => item.id === startMediaId)
    : -1;
  const startIndex = requestedStartIndex >= 0 ? requestedStartIndex : 0;
  const currentIndex = items.length
    ? ((startIndex + playhead) % items.length + items.length) % items.length
    : 0;
  const current = items[currentIndex];
  const next = items.length ? items[(currentIndex + 1) % items.length] : null;
  const intervalMilliseconds = slideshowInterval(searchParams) * 1_000;
  const returnTo = safeReturnPath(searchParams.get("return_to"));

  const advance = useCallback(() => {
    setPlayhead((value) => value + 1);
  }, []);

  const retreat = useCallback(() => {
    setPlayhead((value) => value - 1);
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
    video.muted = !soundEnabled;
    if (paused) {
      video.pause();
      return;
    }
    let cancelled = false;
    void video.play().then(
      () => {
        if (!cancelled) setAudioBlocked(false);
      },
      () => {
        if (!cancelled && soundEnabled) {
          setAudioBlocked(true);
          setControlsVisible(true);
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [current, paused, playhead, soundEnabled]);

  useEffect(() => {
    if (next?.kind !== "image") return;
    const image = new Image();
    image.src = next.playback_url;
  }, [next]);

  function exitSlideshow() {
    const target = new URL(returnTo, "http://gallery.local");
    if (target.searchParams.has("view_media") && current) target.searchParams.set("view_media", current.id);
    navigate(`${target.pathname}${target.search}`, { replace: true });
  }

  const toggleSound = useCallback(() => {
    const video = videoRef.current;
    if (soundEnabled && !audioBlocked) {
      setSoundEnabled(false);
      setAudioBlocked(false);
      if (video) video.muted = true;
      return;
    }

    setSoundEnabled(true);
    setAudioBlocked(false);
    if (!video || current?.kind !== "video" || paused) return;
    video.muted = false;
    void video.play().then(
      () => setAudioBlocked(false),
      () => {
        setAudioBlocked(true);
        setControlsVisible(true);
      },
    );
  }, [audioBlocked, current?.kind, paused, soundEnabled]);

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
        <button className="secondary-button" onClick={exitSlideshow}>
          Return to Library
        </button>
      </main>
    );
  }

  if (!current) {
    return (
      <main className="slideshow-page slideshow-status-page">
        <strong>No media matches this slideshow source.</strong>
        <button className="secondary-button" onClick={exitSlideshow}>
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
            muted={!soundEnabled}
            playsInline
            preload="auto"
            onEnded={advance}
          />
        ) : (
          <img
            className="slideshow-media"
            key={`${current.id}-${playhead}`}
            src={current.playback_url}
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
              ? ` · ${items.length} loaded of ${playlist.data.total}`
              : ""}
            {playlist.data.shuffle ? " · shuffled" : ""}
          </span>
        </div>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={exitSlideshow}
        >
          Exit
        </button>
      </div>

      <div className="slideshow-controls" aria-hidden={!controlsVisible}>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={retreat}
        >
          Previous
        </button>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={() => setPaused((value) => !value)}
        >
          {paused ? "Resume" : "Pause"}
        </button>
        <button
          className="slideshow-control"
          type="button"
          tabIndex={controlsVisible ? 0 : -1}
          onClick={advance}
        >
          Next
        </button>
        {current.kind === "video" ? (
          <button
            className="slideshow-control"
            type="button"
            tabIndex={controlsVisible ? 0 : -1}
            aria-pressed={soundEnabled && !audioBlocked}
            onClick={toggleSound}
          >
            {soundEnabled && !audioBlocked ? "Mute" : "Enable sound"}
          </button>
        ) : null}
      </div>
    </main>
  );
}

function slideshowInterval(search: URLSearchParams): number {
  const value = Number(search.get("interval"));
  return [5, 8, 12, 20].includes(value) ? value : 8;
}

function safeReturnPath(value: string | null): string {
  const browse = safeBrowseHref(value);
  if (browse) return browse;
  if (value?.startsWith("/") && !value.startsWith("//")) {
    try {
      const url = new URL(value, "http://gallery.local");
      if (url.origin === "http://gallery.local" && /^\/(library|review)\/[^/]+$/.test(url.pathname)) return `${url.pathname}${url.search}`;
    } catch { /* Malformed return paths must not prevent playback. */ }
  }
  return "/library";
}

function videoFallbackMilliseconds(item: SlideshowItem): number {
  const expectedDuration = (item.duration_seconds ?? 120) * 1_000;
  return Math.max(30_000, expectedDuration + 15_000);
}
