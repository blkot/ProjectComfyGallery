import { mediaDetailHref, mediaListQuery, mediaNavigationQuery, mediaPageSize, parseOffset, slideshowHref } from "./media-view";

export type MediaBrowseKind = "library" | "prompt";

export function safeBrowseHref(value: string | null): string | null {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return null;
  try {
    const url = new URL(value, "http://gallery.local");
    if (url.origin !== "http://gallery.local" || !["/library", "/registries/prompts"].includes(url.pathname)) return null;
    return `${url.pathname}${url.search}`;
  } catch { return null; }
}

export function browseScope(kind: MediaBrowseKind, search: URLSearchParams): URLSearchParams {
  if (kind === "library") return mediaNavigationQuery(search);
  const scope = new URLSearchParams({ prompt_id: search.get("prompt_id") ?? "" });
  for (const key of ["preferred_character_lora", "character_lora"]) {
    const value = search.get(key);
    if (value) scope.set(key, value);
  }
  return scope;
}

export function browseNavigationPath(kind: MediaBrowseKind, id: string, scope: URLSearchParams): string {
  if (kind === "library") return `/api/v1/media/${id}/navigation?${scope}`;
  const params = new URLSearchParams(scope);
  params.set("media_id", id);
  return `/api/v1/prompt-registry/usage/navigation?${params}`;
}

export function browsePageQuery(kind: MediaBrowseKind, search: URLSearchParams, position?: number | null): URLSearchParams {
  const params = kind === "library" ? mediaListQuery(search) : browseScope(kind, search);
  params.set("limit", String(mediaPageSize));
  params.set("offset", String(position && position > 0
    ? Math.floor((position - 1) / mediaPageSize) * mediaPageSize
    : parseOffset(search.get(kind === "library" ? "offset" : "usage_offset"))));
  if (kind === "prompt") params.set("group_by_character", "true");
  return params;
}

export function browseReturnHref(kind: MediaBrowseKind, search: URLSearchParams, id: string, position?: number | null): string {
  const params = new URLSearchParams(search);
  for (const key of ["view_media", "return_to", "panel", "limit"]) params.delete(key);
  params.set("return_media", id);
  if (position && position > 0) params.set(kind === "library" ? "offset" : "usage_offset", String(Math.floor((position - 1) / mediaPageSize) * mediaPageSize));
  return `${kind === "library" ? "/library" : "/registries/prompts"}?${params}`;
}

export function overlayHref(pathname: string, search: URLSearchParams, id: string): string {
  const params = new URLSearchParams(search);
  params.set("view_media", id);
  return `${pathname}?${params}`;
}

export function browseDetailHref(kind: MediaBrowseKind, search: URLSearchParams, id: string, position?: number | null): string {
  const detail = new URL(mediaDetailHref(id, kind === "library" ? search : new URLSearchParams(), position), "http://gallery.local");
  detail.searchParams.set("return_to", browseReturnHref(kind, search, id, position));
  return `${detail.pathname}${detail.search}`;
}

export function browseSlideshowHref(kind: MediaBrowseKind, search: URLSearchParams, id: string, returnTo: string): string {
  if (kind === "library") return slideshowHref(search, { source: "filter", collectionId: "", shuffle: false, intervalSeconds: 8, startMediaId: id, returnTo });
  const params = browseScope(kind, search);
  params.set("source", "prompt");
  params.set("start_media", id);
  params.set("interval", "8");
  params.set("return_to", returnTo);
  return `/slideshow?${params}`;
}
