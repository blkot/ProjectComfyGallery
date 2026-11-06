import { apiRequest, type MediaDetail } from "./api";

export function mediaDetailQuery(mediaId: string) {
  return {
    queryKey: ["media-detail", mediaId] as const,
    queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${mediaId}`),
    staleTime: 30_000,
  };
}

/** Returns a cleanup so fast navigation cannot leave detached videos downloading. */
export function preloadMediaAsset(item: MediaDetail): () => void {
  if (item.kind === "image") {
    const image = new Image();
    image.decoding = "async";
    image.src = item.original_url;
    return () => { image.removeAttribute("src"); };
  }

  const video = document.createElement("video");
  let disposed = false;
  const cleanup = () => {
    if (disposed) return;
    disposed = true;
    window.clearTimeout(timeout);
    video.removeEventListener("loadedmetadata", cleanup);
    video.removeEventListener("error", cleanup);
    video.removeAttribute("src");
    video.load();
  };
  const timeout = window.setTimeout(cleanup, 15_000);
  video.addEventListener("loadedmetadata", cleanup, { once: true });
  video.addEventListener("error", cleanup, { once: true });
  video.preload = "metadata";
  video.src = item.playback_url;
  video.load();
  return cleanup;
}
