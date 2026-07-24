export const mediaPageSize = 48;
export const defaultMediaSort = "file_created_desc";

export function mediaListQuery(search: URLSearchParams): URLSearchParams {
  const result = new URLSearchParams(search);
  result.set("limit", String(mediaPageSize));
  result.set("offset", String(parseOffset(result.get("offset"))));
  result.set("sort", result.get("sort") || defaultMediaSort);
  return result;
}

export function mediaNavigationQuery(search: URLSearchParams): URLSearchParams {
  const result = mediaListQuery(search);
  result.delete("limit");
  result.delete("offset");
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
  return `/library?${result.toString()}`;
}

export function parseOffset(value: string | null): number {
  if (!value) return 0;
  const parsed = Number.parseInt(value, 10);
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : 0;
}
