export const mediaPageSize = 48;
export const defaultMediaSort = "file_created_desc";

export type ReferenceMatch = "any" | "all";

export type LibraryFilterExpression = {
  kind: string | null;
  status: string | null;
  workflow_status: string | null;
  evaluation_state: string | null;
  trash: boolean | null;
  spatial_view_preferred: boolean | null;
  favorite: boolean | null;
  checkpoint_reference_ids: string[];
  checkpoint_reference_match: ReferenceMatch;
  lora_reference_ids: string[];
  lora_reference_match: ReferenceMatch;
};

export function mediaListQuery(search: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams(search);
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
    spatial_view_preferred: booleanFilter(search, "spatial_view_preferred"),
    favorite: booleanFilter(search, "favorite"),
    checkpoint_reference_ids: uniqueValues(
      search.getAll("checkpoint_reference_id"),
    ),
    checkpoint_reference_match: referenceMatch(
      search.get("checkpoint_reference_match"),
    ),
    lora_reference_ids: uniqueValues(search.getAll("lora_reference_id")),
    lora_reference_match: referenceMatch(
      search.get("lora_reference_match"),
    ),
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
  if (position && position > 0) {
    const pageOffset = Math.floor((position - 1) / mediaPageSize) * mediaPageSize;
    result.set("offset", String(pageOffset));
  }
  return `/library/${mediaId}?${result.toString()}`;
}

export function mediaLibraryHref(search: URLSearchParams): string {
  const result = mediaListQuery(search);
  result.delete("limit");
  result.delete("panel");
  return `/library?${result.toString()}`;
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
