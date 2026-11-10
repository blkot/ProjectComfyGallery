import type { ClassifierRating, ClassifierStatus, PromptSource } from "./api";

export const mediaPageSize = 48;
export const defaultMediaSort = "file_created_desc";
export const mediaReturnParam = "return_media";

export type ReferenceMatch = "any" | "all";
export type PaginationItem = number | "start-ellipsis" | "end-ellipsis";
export type SlideshowSource = "filter" | "collection";

export type SlideshowOptions = {
  source: SlideshowSource;
  collectionId: string;
  shuffle: boolean;
  intervalSeconds: number;
  startMediaId?: string;
  returnTo?: string;
};

export type LibraryFilterExpression = {
  q: string | null;
  kind: string | null;
  status: string | null;
  workflow_status: string | null;
  evaluation_state: string | null;
  trash: boolean | null;
  prefer_spatial_playback: boolean | null;
  spatial_available: boolean | null;
  favorite: boolean | null;
  content_rating: "sfw" | "nsfw" | "unknown" | null;
  classifier_status?: ClassifierStatus | null;
  classifier_rating?: ClassifierRating | null;
  prompt_source?: PromptSource | null;
  character_lora?: string;
  checkpoint_reference_ids: string[];
  checkpoint_reference_match: ReferenceMatch;
  lora_reference_ids: string[];
  lora_reference_match: ReferenceMatch;
};

export function mediaListQuery(search: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams(search);
  const promptRegistryContext = [
    "view_media",
    "return_to",
    "usage_offset",
    "preferred_character_lora",
    "prompt_id",
    "heatmap_source",
    "heatmap_character",
    "heatmap_not_faved",
    "heatmap_trash",
  ];
  for (const key of promptRegistryContext) result.delete(key);
  result.delete("classifier_review_queue");
  if (!isPromptSource(result.get("prompt_source"))) {
    result.delete("prompt_source");
  }
  if (
    !result.has("prefer_spatial_playback") &&
    result.has("spatial_view_preferred")
  ) {
    result.set(
      "prefer_spatial_playback",
      result.get("spatial_view_preferred") ?? "",
    );
  }
  result.delete("spatial_view_preferred");
  result.delete(mediaReturnParam);
  normalizeTrashQuery(result);
  result.set("limit", String(mediaPageSize));
  result.set("offset", String(parseOffset(result.get("offset"))));
  result.set("sort", result.get("sort") || defaultMediaSort);
  return result;
}

export function libraryFilterExpression(
  search: URLSearchParams,
): LibraryFilterExpression {
  const characterLora = search.get("character_lora")?.trim();
  return {
    q: search.get("q")?.trim() || null,
    kind: search.get("kind") || null,
    status: search.get("status") || null,
    workflow_status: search.get("workflow_status") || null,
    evaluation_state: search.get("evaluation_state") || null,
    trash: trashFilter(search),
    prefer_spatial_playback:
      booleanFilter(search, "prefer_spatial_playback") ??
      booleanFilter(search, "spatial_view_preferred"),
    spatial_available: booleanFilter(search, "spatial_available"),
    favorite: booleanFilter(search, "favorite"),
    content_rating: contentRatingFilter(search),
    classifier_status: classifierStatusFilter(search),
    classifier_rating: classifierRatingFilter(search),
    prompt_source: promptSourceFilter(search),
    ...(characterLora ? { character_lora: characterLora } : {}),
    checkpoint_reference_ids: uniqueValues(
      search.getAll("checkpoint_reference_id"),
    ),
    checkpoint_reference_match: referenceMatch(
      search.get("checkpoint_reference_match"),
    ),
    lora_reference_ids: uniqueValues(search.getAll("lora_reference_id")),
    lora_reference_match: referenceMatch(search.get("lora_reference_match")),
  };
}

export function mediaNavigationQuery(search: URLSearchParams): URLSearchParams {
  const result = mediaListQuery(search);
  result.delete("limit");
  result.delete("offset");
  result.delete("panel");
  return result;
}

export function photoWallQuery(search: URLSearchParams): URLSearchParams {
  const result = mediaNavigationQuery(search);
  result.set("kind", "image");
  result.delete("return_to");
  return result;
}

export function photoWallHref(search: URLSearchParams): string {
  const result = photoWallQuery(search);
  const returnTo = search.toString()
    ? `/library?${search.toString()}`
    : "/library";
  result.set("return_to", returnTo);
  return `/photo-wall?${result.toString()}`;
}

export function slideshowHref(
  librarySearch: URLSearchParams,
  options: SlideshowOptions,
): string {
  const result =
    options.source === "filter"
      ? mediaNavigationQuery(librarySearch)
      : new URLSearchParams();
  preserveTrashContext(librarySearch, result);
  result.set("source", options.source);
  if (options.source === "collection") {
    result.set("collection_id", options.collectionId);
  }
  result.set("shuffle", String(options.shuffle));
  if (options.shuffle) {
    result.set("random_seed", String(randomSeed()));
  }
  result.set("interval", String(options.intervalSeconds));
  if (options.startMediaId) result.set("start_media", options.startMediaId);
  const returnSearch = new URLSearchParams(librarySearch);
  result.set(
    "return_to",
    options.returnTo ??
      (returnSearch.size ? `/library?${returnSearch.toString()}` : "/library"),
  );
  return `/slideshow?${result.toString()}`;
}

export function reviewSlideshowHref(
  filter: Record<string, unknown>,
  startMediaId: string,
  returnTo: string,
): string {
  return slideshowHref(mediaFilterSearchParams(filter), {
    source: "filter",
    collectionId: "",
    shuffle: false,
    intervalSeconds: 8,
    startMediaId,
    returnTo,
  });
}

export function slideshowPlaylistQuery(
  slideshowSearch: URLSearchParams,
): URLSearchParams {
  const result = new URLSearchParams();
  const source = slideshowSearch.get("source");
  if (source === "collection") {
    copySingle(slideshowSearch, result, "collection_id");
    copySingle(slideshowSearch, result, "trash");
  } else {
    for (const name of slideshowFilterParameters) {
      copyAll(slideshowSearch, result, name);
    }
  }
  copySingle(slideshowSearch, result, "sort");
  copySingle(slideshowSearch, result, "shuffle");
  copySingle(slideshowSearch, result, "random_seed");
  const startMediaId = slideshowSearch.get("start_media");
  if (startMediaId) result.set("start_media_id", startMediaId);
  normalizeTrashQuery(result);
  result.set("limit", "2000");
  return result;
}

export function mediaDetailHref(
  mediaId: string,
  search: URLSearchParams,
  position?: number | null,
): string {
  const result = mediaListQuery(search);
  if (search.has("return_to")) result.set("return_to", search.get("return_to")!);
  preserveTrashContext(search, result);
  result.set(mediaReturnParam, mediaId);
  if (position && position > 0) {
    const pageOffset =
      Math.floor((position - 1) / mediaPageSize) * mediaPageSize;
    result.set("offset", String(pageOffset));
  }
  return `/library/${mediaId}?${result.toString()}`;
}

export function mediaLibraryHref(search: URLSearchParams): string {
  const returnMediaId = search.get(mediaReturnParam);
  const result = mediaListQuery(search);
  preserveTrashContext(search, result);
  result.delete("limit");
  result.delete("panel");
  if (returnMediaId) result.set(mediaReturnParam, returnMediaId);
  return `/library?${result.toString()}`;
}

export function pageOffsetForNumber(pageNumber: number, total: number): number {
  const pageCount = Math.max(1, Math.ceil(total / mediaPageSize));
  const requestedPage = Number.isFinite(pageNumber)
    ? Math.trunc(pageNumber)
    : 1;
  const page = Math.min(Math.max(requestedPage, 1), pageCount);
  return (page - 1) * mediaPageSize;
}

export function paginationItems(
  currentPage: number,
  pageCount: number,
): PaginationItem[] {
  const totalPages = Math.max(1, Math.trunc(pageCount));
  const activePage = Math.min(
    Math.max(Math.trunc(currentPage) || 1, 1),
    totalPages,
  );
  if (totalPages <= 9) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  let windowStart = Math.max(2, activePage - 2);
  let windowEnd = Math.min(totalPages - 1, activePage + 2);
  if (activePage <= 4) {
    windowStart = 2;
    windowEnd = 6;
  } else if (activePage >= totalPages - 3) {
    windowStart = totalPages - 5;
    windowEnd = totalPages - 1;
  }

  const items: PaginationItem[] = [1];
  if (windowStart > 2) items.push("start-ellipsis");
  for (let page = windowStart; page <= windowEnd; page += 1) {
    items.push(page);
  }
  if (windowEnd < totalPages - 1) items.push("end-ellipsis");
  items.push(totalPages);
  return items;
}

export function parseOffset(value: string | null): number {
  if (!value) return 0;
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}

function referenceMatch(value: string | null): ReferenceMatch {
  return value === "all" ? "all" : "any";
}

function trashFilter(search: URLSearchParams): boolean | null {
  const value = search.get("trash");
  if (value === "all") return null;
  return value === "true" ? true : false;
}

function normalizeTrashQuery(search: URLSearchParams): void {
  if (search.get("trash") === "all") {
    search.delete("trash");
    return;
  }
  search.set("trash", search.get("trash") === "true" ? "true" : "false");
}

function preserveTrashContext(
  source: URLSearchParams,
  destination: URLSearchParams,
): void {
  const value = source.get("trash");
  destination.set(
    "trash",
    value === "all" || value === "true" ? value : "false",
  );
}

function booleanFilter(search: URLSearchParams, name: string): boolean | null {
  return search.has(name) ? search.get(name) === "true" : null;
}

function contentRatingFilter(
  search: URLSearchParams,
): "sfw" | "nsfw" | "unknown" | null {
  const value = search.get("content_rating");
  return value === "sfw" || value === "nsfw" || value === "unknown"
    ? value
    : null;
}

function classifierStatusFilter(search: URLSearchParams): ClassifierStatus | null {
  const value = search.get("classifier_status");
  return value &&
    [
      "unclassified",
      "suggested",
      "needs_review",
      "reviewed",
      "processing",
      "failed",
    ].includes(value)
    ? (value as ClassifierStatus)
    : null;
}

function classifierRatingFilter(search: URLSearchParams): ClassifierRating | null {
  const value = search.get("classifier_rating");
  return value && ["safe", "sexy", "nudity", "explicit", "review"].includes(value)
    ? (value as ClassifierRating)
    : null;
}

function promptSourceFilter(search: URLSearchParams): PromptSource | null {
  const value = search.get("prompt_source");
  return isPromptSource(value) ? value : null;
}

function isPromptSource(value: string | null): value is PromptSource {
  return value === "api_prompt" || value === "visual_workflow";
}

function uniqueValues(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

const slideshowFilterParameters = [
  "q",
  "sha256",
  "kind",
  "status",
  "workflow_status",
  "evaluation_state",
  "trash",
  "prefer_spatial_playback",
  "spatial_available",
  "favorite",
  "content_rating",
  "classifier_status",
  "classifier_rating",
  "prompt_source",
  "character_lora",
  "source_root_id",
  "collection_id",
  "tag_id",
  "checkpoint_reference_id",
  "checkpoint_reference_match",
  "lora_reference_id",
  "lora_reference_match",
] as const;

export function mediaFilterSearchParams(
  filter: Record<string, unknown>,
): URLSearchParams {
  const result = new URLSearchParams();
  for (const [rawName, value] of Object.entries(filter)) {
    const name = reviewFilterParameterName(rawName);
    if (value === null || value === undefined || value === "") continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== null && item !== undefined && item !== "") {
          result.append(name, String(item));
        }
      }
      continue;
    }
    result.set(name, String(value));
  }
  return result;
}

function reviewFilterParameterName(name: string): string {
  if (name === "checkpoint_reference_ids") return "checkpoint_reference_id";
  if (name === "lora_reference_ids") return "lora_reference_id";
  return name;
}

function copySingle(
  source: URLSearchParams,
  destination: URLSearchParams,
  name: string,
) {
  const value = source.get(name);
  if (value) destination.set(name, value);
}

function copyAll(
  source: URLSearchParams,
  destination: URLSearchParams,
  name: string,
) {
  for (const value of source.getAll(name)) {
    if (value) destination.append(name, value);
  }
}

function randomSeed(): number {
  const values = new Uint32Array(1);
  globalThis.crypto.getRandomValues(values);
  return values[0] & 0x7fffffff;
}
