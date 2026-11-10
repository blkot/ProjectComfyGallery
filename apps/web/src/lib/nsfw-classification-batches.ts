import type { MediaPage } from "./api";
import type { LibrarySelection } from "./library-selection";
import { defaultMediaSort, mediaFilterSearchParams } from "./media-view";

export const nsfwClassificationBatchSize = 2000;
export const mediaIdResolutionPageSize = 200;

export function splitMediaIds(mediaIds: string[], batchSize = nsfwClassificationBatchSize) {
  if (!Number.isInteger(batchSize) || batchSize < 1) {
    throw new RangeError("The classification batch size must be a positive integer.");
  }

  const batches: string[][] = [];
  for (let offset = 0; offset < mediaIds.length; offset += batchSize) {
    batches.push(mediaIds.slice(offset, offset + batchSize));
  }
  return batches;
}

export async function resolveFilteredSelectionMediaIds(
  selection: Extract<LibrarySelection, { mode: "filter" }>,
  fetchPage: (path: string) => Promise<MediaPage>,
): Promise<string[]> {
  const query = mediaFilterSearchParams(selection.filter);
  query.set("sort", defaultMediaSort);
  query.set("limit", String(mediaIdResolutionPageSize));

  const mediaIds: string[] = [];
  let offset = 0;
  let total = selection.count;
  while (offset < total) {
    query.set("offset", String(offset));
    const page = await fetchPage(`/api/v1/media?${query.toString()}`);
    total = page.total;
    if (!page.items.length) break;
    for (const item of page.items) {
      if (!selection.excludedIds.has(item.id)) mediaIds.push(item.id);
    }
    offset += page.items.length;
  }
  return mediaIds;
}
