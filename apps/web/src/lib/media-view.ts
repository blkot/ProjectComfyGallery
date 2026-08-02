export const mediaPageSize = 48;
export const defaultMediaSort = "file_created_desc";
export const mediaReturnParam = "return_media";

export type ReferenceMatch = "any" | "all";
export type PaginationItem = number | "start-ellipsis" | "end-ellipsis";

export type LibraryFilterExpression = {
  kind: string | null;
  status: string | null;
  workflow_status: string | null;
  evaluation_state: string | null;
  trash: boolean | null;
  prefer_spatial_playback: boolean | null;
  spatial_available: boolean | null;
  favorite: boolean | null;
  checkpoint_reference_ids: string[];
  checkpoint_reference_match: ReferenceMatch;
  lora_reference_ids: string[];
  lora_reference_match: ReferenceMatch;
};

export function mediaListQuery(search: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams(search);
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
  result.set("limit", String(mediaPageSize));
  result.set("offset", String(parseOffset(result.get("offset"))));
  result.set("sort", result.get("sort") || defaultMediaSort);
  return result;
}

export function libraryFilterExpression(
  search: URLSearchParams,
): LibraryFilterExpression {
  return {
    kind: search.get("kind") || null,
    status: search.get("status") || null,
    workflow_status: search.get("workflow_status") || null,
    evaluation_state: search.get("evaluation_state") || null,
    trash: search.has("trash") ? search.get("trash") === "true" : null,
    prefer_spatial_playback:
      booleanFilter(search, "prefer_spatial_playback") ??
      booleanFilter(search, "spatial_view_preferred"),
    spatial_available: booleanFilter(search, "spatial_available"),
    favorite: booleanFilter(search, "favorite"),
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

export function mediaDetailHref(
  mediaId: string,
  search: URLSearchParams,
  position?: number | null,
): string {
  const result = mediaListQuery(search);
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

function booleanFilter(search: URLSearchParams, name: string): boolean | null {
  return search.has(name) ? search.get(name) === "true" : null;
}

function uniqueValues(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}
