import type { LibraryFilterExpression } from "./media-view";

export type LibrarySelection =
  | { mode: "browse" }
  | { mode: "explicit"; mediaIds: Set<string> }
  | {
      mode: "filter";
      filter: LibraryFilterExpression;
      count: number;
      excludedIds: Set<string>;
    };

export type MediaSelectionPayload =
  | { media_ids: string[] }
  | {
      filter: LibraryFilterExpression;
      exclude_media_ids?: string[];
    };

export const emptyLibrarySelection = (): LibrarySelection => ({
  mode: "browse",
});

export function isSelectionActive(selection: LibrarySelection): boolean {
  return selection.mode !== "browse";
}

export function selectionCount(selection: LibrarySelection): number {
  if (selection.mode === "browse") return 0;
  if (selection.mode === "explicit") return selection.mediaIds.size;
  return Math.max(0, selection.count - selection.excludedIds.size);
}

export function isMediaSelected(
  selection: LibrarySelection,
  mediaId: string,
): boolean {
  if (selection.mode === "browse") return false;
  if (selection.mode === "explicit") return selection.mediaIds.has(mediaId);
  return !selection.excludedIds.has(mediaId);
}

export function toggleMedia(
  selection: LibrarySelection,
  mediaId: string,
): LibrarySelection {
  if (selection.mode === "browse") {
    return { mode: "explicit", mediaIds: new Set([mediaId]) };
  }

  if (selection.mode === "explicit") {
    const mediaIds = new Set(selection.mediaIds);
    if (mediaIds.has(mediaId)) mediaIds.delete(mediaId);
    else mediaIds.add(mediaId);
    return mediaIds.size
      ? { mode: "explicit", mediaIds }
      : emptyLibrarySelection();
  }

  const excludedIds = new Set(selection.excludedIds);
  if (excludedIds.has(mediaId)) excludedIds.delete(mediaId);
  else excludedIds.add(mediaId);
  return selectionCount({ ...selection, excludedIds })
    ? { ...selection, excludedIds }
    : emptyLibrarySelection();
}

export function togglePage(
  selection: LibrarySelection,
  mediaIds: string[],
): LibrarySelection {
  if (!mediaIds.length) return selection;

  if (selection.mode === "browse") {
    return { mode: "explicit", mediaIds: new Set(mediaIds) };
  }

  if (selection.mode === "explicit") {
    const next = new Set(selection.mediaIds);
    const pageIsSelected = mediaIds.every((mediaId) => next.has(mediaId));
    for (const mediaId of mediaIds) {
      if (pageIsSelected) next.delete(mediaId);
      else next.add(mediaId);
    }
    return next.size
      ? { mode: "explicit", mediaIds: next }
      : emptyLibrarySelection();
  }

  const pageIsSelected = mediaIds.every(
    (mediaId) => !selection.excludedIds.has(mediaId),
  );
  const excludedIds = new Set(selection.excludedIds);
  for (const mediaId of mediaIds) {
    if (pageIsSelected) excludedIds.add(mediaId);
    else excludedIds.delete(mediaId);
  }
  return selectionCount({ ...selection, excludedIds })
    ? { ...selection, excludedIds }
    : emptyLibrarySelection();
}

export function selectAllMatching(
  filter: LibraryFilterExpression,
  count: number,
): LibrarySelection {
  return {
    mode: "filter",
    filter: {
      ...filter,
      checkpoint_reference_ids: [...filter.checkpoint_reference_ids],
      lora_reference_ids: [...filter.lora_reference_ids],
    },
    count,
    excludedIds: new Set(),
  };
}

export function selectionPayload(
  selection: LibrarySelection,
): MediaSelectionPayload {
  if (selection.mode === "filter") {
    const excludedIds = [...selection.excludedIds];
    return {
      filter: selection.filter,
      ...(excludedIds.length ? { exclude_media_ids: excludedIds } : {}),
    };
  }
  return {
    media_ids: selection.mode === "explicit" ? [...selection.mediaIds] : [],
  };
}
