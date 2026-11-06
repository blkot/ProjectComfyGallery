import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type MouseEvent,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";

import {
  apiRequest,
  type MediaDetail,
  type MediaNavigation,
  type PromptRegistryLookup,
  type WorkflowDetail,
  type WorkflowDisplayField,
} from "../lib/api";
import { copyText } from "../lib/clipboard";
import { hasShortcutModifier, isShortcutBlockedTarget } from "../lib/keyboard";
import { mediaDetailQuery, preloadMediaAsset } from "../lib/media-detail-query";
import { LoraListValue } from "./lora-list-value";
import { MediaActionToolbar } from "./media-action-toolbar";
import { MediaImageStage } from "./media-image-stage";
import "./media-quick-view.css";

export type MediaQuickViewProps = {
  mediaId: string;
  navigation?: MediaNavigation;
  navigationPending?: boolean;
  navigationError?: boolean;
  navigationOutsideScope?: boolean;
  onSeek: (id: string, position: number | null) => void;
  onClose: () => void;
  fullDetailHref: string;
  slideshowHref: string;
  civitaiHref: string;
};

export function MediaQuickView({
  mediaId,
  navigation,
  navigationPending = false,
  navigationError = false,
  navigationOutsideScope = false,
  onSeek,
  onClose,
  fullDetailHref,
  slideshowHref,
  civitaiHref,
}: MediaQuickViewProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const favoriteButtonRef = useRef<HTMLButtonElement>(null);
  const ratingButtonRef = useRef<HTMLButtonElement>(null);
  const backdropPress = useRef(false);
  const lastWheelAt = useRef(0);
  const queryClient = useQueryClient();
  const media = useQuery(mediaDetailQuery(mediaId));
  const [readyImageId, setReadyImageId] = useState<string | null>(null);
  const frameReady = media.data?.id === mediaId && (media.data.kind === "video" || readyImageId === mediaId);
  const currentNavigation = navigation?.media_id === mediaId ? navigation : undefined;
  const navigationBlocked = navigationPending || (navigationError && !navigationOutsideScope);
  const previousId = navigationBlocked ? null : currentNavigation?.previous_id;
  const nextId = navigationBlocked ? null : currentNavigation?.next_id;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    const previousOverflow = document.body.style.overflow;
    const previousGutter = document.documentElement.style.scrollbarGutter;
    document.documentElement.style.scrollbarGutter = "stable";
    document.body.style.overflow = "hidden";
    dialog.showModal();
    dialog.focus({ preventScroll: true });
    return () => {
      dialog.close();
      document.body.style.overflow = previousOverflow;
      document.documentElement.style.scrollbarGutter = previousGutter;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const cleanups: Array<() => void> = [];
    for (const id of new Set([previousId, nextId])) {
      if (!id) continue;
      void queryClient.ensureQueryData(mediaDetailQuery(id)).then((item) => {
        if (!cancelled) cleanups.push(preloadMediaAsset(item));
      }, () => undefined);
    }
    return () => {
      cancelled = true;
      for (const cleanup of cleanups) cleanup();
    };
  }, [previousId, nextId, queryClient]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    function onKeyDown(event: KeyboardEvent) {
      if (
        event.repeat || hasShortcutModifier(event) ||
        isQuickViewInteractiveTarget(event.target)
      ) return;

      if (event.key === "ArrowLeft" && previousId) {
        event.preventDefault();
        event.stopPropagation();
        onSeek(previousId, currentNavigation?.previous_position ?? null);
      } else if (event.key === "ArrowRight" && nextId) {
        event.preventDefault();
        event.stopPropagation();
        onSeek(nextId, currentNavigation?.next_position ?? null);
      } else if (event.key.toLowerCase() === "f") {
        if (!frameReady) return;
        event.preventDefault();
        event.stopPropagation();
        favoriteButtonRef.current?.click();
      } else if (event.key.toLowerCase() === "n") {
        if (!frameReady) return;
        event.preventDefault();
        event.stopPropagation();
        ratingButtonRef.current?.click();
      } else if (event.code === "Space" && videoRef.current) {
        event.preventDefault();
        const video = videoRef.current;
        if (video.paused) void video.play().catch(() => undefined);
        else video.pause();
      }
    }
    dialog.addEventListener("keydown", onKeyDown);
    return () => dialog.removeEventListener("keydown", onKeyDown);
  }, [currentNavigation, previousId, nextId, onSeek, frameReady]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    function onWheel(event: WheelEvent) {
      // Native video controls must retain their own pointer/volume behavior.
      if (
        isQuickViewInteractiveTarget(event.target) ||
        event.ctrlKey || event.altKey || event.metaKey || event.shiftKey || event.deltaY === 0 ||
        Math.abs(event.deltaY) < Math.abs(event.deltaX)
      ) return;
      event.preventDefault();
      const now = Date.now();
      if (now - lastWheelAt.current < 350) return;
      const id = event.deltaY > 0 ? nextId : previousId;
      if (!id) return;
      lastWheelAt.current = now;
      onSeek(id, event.deltaY > 0
        ? currentNavigation?.next_position ?? null
        : currentNavigation?.previous_position ?? null);
    }
    // React's delegated wheel listener is passive; this local handler can consume
    // a navigation gesture without letting the browser also scroll the preview.
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [currentNavigation, previousId, nextId, onSeek]);

  function outsideDialog(event: MouseEvent<HTMLDialogElement>) {
    if (event.target !== event.currentTarget) return false;
    const rect = event.currentTarget.getBoundingClientRect();
    return event.clientX < rect.left || event.clientX > rect.right ||
      event.clientY < rect.top || event.clientY > rect.bottom;
  }

  return createPortal(
    <dialog
      ref={dialogRef}
      className="media-quick-view"
      aria-labelledby={titleId}
      aria-keyshortcuts="ArrowLeft ArrowRight F N Escape"
      tabIndex={-1}
      onCancel={(event) => { event.preventDefault(); onClose(); }}
      onMouseDown={(event) => { backdropPress.current = outsideDialog(event); }}
      onClick={(event) => {
        if (backdropPress.current && outsideDialog(event)) onClose();
        backdropPress.current = false;
      }}
    >
      <header className="media-quick-view-toolbar">
        <nav className="media-quick-view-navigation" aria-label="Quick view navigation">
          <button type="button" aria-label="Previous media" title="Previous media (←)"
            disabled={!previousId}
            onClick={() => previousId && onSeek(previousId, currentNavigation?.previous_position ?? null)}>
            <Arrow direction="previous" />
          </button>
          <span aria-live="polite">
            {navigationOutsideScope ? "Outside view" : navigationError ? "Navigation unavailable" : currentNavigation
              ? `${currentNavigation.position} / ${currentNavigation.total}` : "Locating…"}
          </span>
          <button type="button" aria-label="Next media" title="Next media (→)"
            disabled={!nextId}
            onClick={() => nextId && onSeek(nextId, currentNavigation?.next_position ?? null)}>
            <Arrow direction="next" />
          </button>
        </nav>
        {media.data ? (
          <fieldset className="media-quick-view-actions" disabled={!frameReady} inert={!frameReady || undefined}
            aria-busy={!frameReady} aria-label={!frameReady ? "Media actions unavailable while image loads" : undefined}>
            <MediaActionToolbar media={media.data} slideshowHref={slideshowHref}
            civitaiHref={civitaiHref} favoriteButtonRef={favoriteButtonRef}
            contentRatingShortcutRef={ratingButtonRef} />
          </fieldset>
        ) : <span className="media-quick-view-toolbar-space" />}
        <div className="media-quick-view-exit-actions">
          <Link to={fullDetailHref} aria-label="Open full details" title="Open full details">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M10 4H4v16h16v-6" /></svg>
          </Link>
          <button type="button" aria-label="Close media preview" title="Close (Esc)" onClick={onClose}>
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18" /></svg>
          </button>
        </div>
      </header>
      <div className="media-quick-view-body">
        <div ref={stageRef} className="media-quick-view-stage" aria-label="Media preview" tabIndex={0}
          onMouseDown={(event) => {
            if (event.button === 1 && !isQuickViewInteractiveTarget(event.target)) event.preventDefault();
          }}
          onAuxClick={(event) => {
            if (event.button !== 1 || isQuickViewInteractiveTarget(event.target)) return;
            event.preventDefault();
            if (!frameReady) return;
            favoriteButtonRef.current?.click();
          }}>
          {media.data?.kind === "video"
            ? <QuickViewVideo key={mediaId} media={media.data} videoRef={videoRef} />
            : <MediaImageStage mediaId={mediaId} media={media.data} failed={media.isError} onReady={setReadyImageId}
              onRetry={() => void media.refetch()} />}
        </div>
        <aside className="media-quick-view-information" aria-label="Media information" key={mediaId}>
          <h2 id={titleId} className="media-quick-view-filename">{media.data?.original_filename ?? "Media preview"}</h2>
          {navigationOutsideScope ? <p className="media-quick-view-scope-notice" role="status">
            This media is no longer in the current view. You can undo the change, continue browsing, or close the preview.
          </p> : navigationError ? <p className="media-quick-view-scope-notice" role="status">
            Navigation could not be loaded. The media remains open.
          </p> : null}
          <QuickViewMetadata mediaId={mediaId} dialogRef={dialogRef} />
        </aside>
      </div>
    </dialog>,
    document.body,
  );
}

function Arrow({ direction }: { direction: "previous" | "next" }) {
  return <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d={direction === "previous" ? "m14 6-6 6 6 6" : "m10 6 6 6-6 6"} />
  </svg>;
}

function isQuickViewInteractiveTarget(target: EventTarget | null): boolean {
  return isShortcutBlockedTarget(target) || (target instanceof Element && Boolean(
    target.closest("video, button, a, input, select, textarea, summary, [contenteditable='true']"),
  ));
}

function QuickViewVideo({ media, videoRef }: {
  media: MediaDetail;
  videoRef: RefObject<HTMLVideoElement | null>;
}) {
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const video = videoRef.current;
    return () => {
      if (!video) return;
      video.pause();
      video.removeAttribute("src");
      video.load();
    };
  }, [videoRef]);
  return <>
    <video ref={videoRef} src={media.playback_url} controls playsInline preload="metadata"
        poster={media.preview_url} aria-label={media.original_filename} onError={() => setFailed(true)} />
    {failed ? <p className="media-quick-view-asset-error" role="alert">
      The original media could not be loaded. <a href={media.original_url}>Open original</a>
    </p> : null}
  </>;
}

function textField(field: WorkflowDisplayField | undefined): string {
  return typeof field?.value === "string" ? field.value.trim() : "";
}

function QuickViewMetadata({ mediaId, dialogRef }: {
  mediaId: string;
  dialogRef: RefObject<HTMLDialogElement | null>;
}) {
  const queryClient = useQueryClient();
  const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");
  const workflow = useQuery({
    queryKey: ["media-workflow-summary", mediaId],
    queryFn: () => apiRequest<WorkflowDetail>(`/api/v1/media/${mediaId}/workflow?node_limit=1&edge_limit=1`),
    staleTime: 30_000,
  });
  const fields = workflow.data?.display_fields;
  const promptId = textField(fields?.prompt_id);
  const registry = useQuery({
    queryKey: ["prompt-registry-lookup", promptId],
    queryFn: () => apiRequest<PromptRegistryLookup>(
      `/api/v1/prompt-registry/lookup?prompt_id=${encodeURIComponent(promptId)}&limit=1`,
    ),
    enabled: Boolean(promptId),
    staleTime: 60_000,
    initialData: () => {
      const direct = queryClient.getQueriesData<PromptRegistryLookup>({
        queryKey: ["prompt-registry-lookup", promptId],
      }).find(([, data]) => data !== undefined)?.[1];
      return direct ?? queryClient.getQueriesData<PromptRegistryLookup>({
        queryKey: ["prompt-registry-usage"],
      }).find(([, data]) => data && samePromptIdentifier(promptId, data))?.[1];
    },
  });
  const prompt = registry.data?.entry?.prompt ?? "";

  return <>
    {workflow.isPending ? <p className="muted" role="status">Loading metadata…</p> : null}
    {workflow.isError ? <p className="notice error-notice" role="alert">
      Metadata could not be loaded. <button type="button" onClick={() => void workflow.refetch()}>Retry</button>
    </p> : null}
    <section className="media-quick-view-field">
      <h3>Prompt ID</h3>
      {promptId ? <Link to={`/registries/prompts?prompt_id=${encodeURIComponent(promptId)}`}
        className="media-quick-view-prompt-id">{promptId}</Link>
        : <p className="media-quick-view-unavailable">
          {workflow.isPending ? "—" : workflow.isError ? "Unavailable" : "Not recorded"}
        </p>}
    </section>
    <section className="media-quick-view-field">
      <h3>Character LoRA</h3>
      <p className="media-quick-view-character">{textField(fields?.character_lora) || "—"}</p>
    </section>
    <details className="media-quick-view-loras">
      <summary>LoRA list{Array.isArray(fields?.lora_list?.value) ? ` · ${fields.lora_list.value.length}` : ""}</summary>
      {fields?.lora_list ? <LoraListValue value={fields.lora_list.value} />
        : <p className="media-quick-view-unavailable">
          {workflow.isPending ? "Loading metadata…" : workflow.isError ? "Metadata unavailable." : "No LoRA list recorded."}
        </p>}
    </details>
    <section className="media-quick-view-field media-quick-view-prompt">
      <div className="media-quick-view-field-heading">
        <h3>Positive Prompt</h3>
        <button className="media-quick-view-copy" type="button" disabled={!prompt || registry.isError}
          aria-label="Copy positive prompt" title="Copy registry prompt" onClick={() => {
            void copyText(prompt, dialogRef.current ?? document.body).then(
              () => setCopyState("copied"), () => setCopyState("error"),
            );
          }}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2" /><path d="M16 8V4H4v12h4" /></svg>
        </button>
      </div>
      {promptId ? registry.isPending ? <p className="media-quick-view-unavailable" role="status">Loading registry prompt…</p>
        : registry.isError ? <p className="notice error-notice" role="alert">
          Registry prompt could not be loaded. <button type="button" onClick={() => void registry.refetch()}>Retry</button>
        </p> : !registry.data?.entry ? <p className="media-quick-view-unavailable">This Prompt ID is not registered.</p>
          : !prompt ? <p className="media-quick-view-unavailable">The registered positive prompt is empty.</p>
            : <><small className="media-quick-view-prompt-source">Prompt Registry</small><pre>{prompt}</pre></>
        : <p className="media-quick-view-unavailable">
          {workflow.isPending ? "—" : workflow.isError
            ? "Prompt lookup is unavailable until metadata can be loaded."
            : "A recorded Prompt ID is needed to resolve the registry prompt."}
        </p>}
      {copyState === "copied" ? <span className="media-quick-view-copy-feedback" role="status">Copied</span> : null}
      {copyState === "error" ? <span className="media-quick-view-copy-feedback" role="alert">Copy failed. Select the prompt text to copy it manually.</span> : null}
    </section>
  </>;
}

function samePromptIdentifier(promptId: string, lookup: PromptRegistryLookup): boolean {
  if (lookup.prompt_id === promptId) return true;
  // The API displays "source - index" and preserves registry zero-padding;
  // workflow save nodes may instead use "source-index" or a different padding.
  const match = /^\s*(.+?)\s*-\s*(\d+)\s*$/.exec(promptId);
  if (!match) return false;
  const source = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();
  const index = (value: string) => value.replace(/^0+/, "") || "0";
  return source(match[1]) === source(lookup.source) && index(match[2]) === index(lookup.index);
}
