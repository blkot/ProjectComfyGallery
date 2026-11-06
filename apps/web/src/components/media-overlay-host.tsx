import { lazy, Suspense } from "react";
import type { useMediaOverlay } from "../lib/use-media-overlay";

const MediaQuickView = lazy(() => import("./media-quick-view").then((module) => ({ default: module.MediaQuickView })));

export function MediaOverlayHost({ overlay }: { overlay: ReturnType<typeof useMediaOverlay> }) {
  return <>
    {overlay.restoring ? <p className="notice" role="status">Locating last viewed media…</p> : null}
    {overlay.notice ? <p className="notice" role="status">{overlay.notice}</p> : null}
    {overlay.restoreError ? <p className="notice error-notice" role="alert">{overlay.restoreError} <button type="button" onClick={overlay.retryRestore}>Retry</button></p> : null}
    {overlay.mediaId ? <Suspense fallback={<p className="notice" role="status">Opening media… <button type="button" onClick={overlay.close}>Cancel</button></p>}>
      <MediaQuickView
        mediaId={overlay.mediaId}
        navigation={overlay.navigation.data}
        navigationPending={overlay.navigation.isPending}
        navigationError={overlay.navigation.isError}
        navigationOutsideScope={Boolean(overlay.navigation.error && "status" in overlay.navigation.error && overlay.navigation.error.status === 404)}
        onSeek={overlay.seek}
        onClose={overlay.close}
        fullDetailHref={overlay.fullDetailHref}
        slideshowHref={overlay.slideshowHref}
        civitaiHref={overlay.civitaiHref}
      />
    </Suspense> : null}
  </>;
}
