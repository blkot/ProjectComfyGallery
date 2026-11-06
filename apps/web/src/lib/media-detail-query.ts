import { apiRequest, type MediaDetail } from "./api";

export function mediaDetailQuery(mediaId: string) {
  return {
    queryKey: ["media-detail", mediaId] as const,
    queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${mediaId}`),
    staleTime: 30_000,
  };
}

// Keep a small decoded working set, not an entire gallery. Immutable original URLs
// let callers share a warm resource when a neighbor becomes the active media.
const imagePreloads = new Map<string, { image: HTMLImageElement; bytes: number }>();
const maximumWarmImages = 4;
const maximumDecodedBytes = 128 * 1024 * 1024;

export function clearMediaAssetPreloads(): void {
  for (const { image } of imagePreloads.values()) image.removeAttribute("src");
  imagePreloads.clear();
}

function trimImagePreloads() {
  let bytes = [...imagePreloads.values()].reduce((sum, entry) => sum + entry.bytes, 0);
  while (imagePreloads.size > maximumWarmImages || bytes > maximumDecodedBytes) {
    const oldest = imagePreloads.entries().next().value;
    if (!oldest) break;
    imagePreloads.delete(oldest[0]);
    oldest[1].image.removeAttribute("src");
    bytes -= oldest[1].bytes;
  }
}

/** Images use a bounded warm cache; detached videos retain explicit cleanup. */
export function preloadMediaAsset(item: MediaDetail): () => void {
  if (item.kind === "image") {
    const existing = imagePreloads.get(item.original_url);
    if (existing) {
      imagePreloads.delete(item.original_url);
      imagePreloads.set(item.original_url, existing);
      return () => undefined;
    }
    const bytes = item.width && item.height ? item.width * item.height * 4 : 16 * 1024 * 1024;
    if (bytes > maximumDecodedBytes) return () => undefined;
    const image = new Image();
    const entry = { image, bytes };
    imagePreloads.set(item.original_url, entry);
    trimImagePreloads();
    image.addEventListener("load", () => {
      if (imagePreloads.get(item.original_url) !== entry) return;
      entry.bytes = image.naturalWidth * image.naturalHeight * 4 || entry.bytes;
      trimImagePreloads();
      if (imagePreloads.get(item.original_url) === entry && image.decode) {
        void image.decode().catch(() => undefined);
      }
    }, { once: true });
    image.addEventListener("error", () => {
      if (imagePreloads.get(item.original_url) === entry) imagePreloads.delete(item.original_url);
    }, { once: true });
    image.decoding = "async";
    image.src = item.original_url;
    // A seek cleans up the old neighbor effect just as its original is promoted.
    // Do not abort that shared request; LRU/budget eviction bounds retained work.
    return () => undefined;
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
