const storagePrefix = "comfy-gallery.classifier-review-queue.v1.";

export type ClassifierReviewQueue = {
  id: string;
  mediaIds: string[];
  createdAt: string;
  sourceTotal: number;
  truncated: boolean;
};

export function saveClassifierReviewQueue(
  mediaIds: string[],
  options: { sourceTotal: number; truncated: boolean },
): string {
  const id =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const queue: ClassifierReviewQueue = {
    id,
    mediaIds: [...new Set(mediaIds)],
    createdAt: new Date().toISOString(),
    sourceTotal: options.sourceTotal,
    truncated: options.truncated,
  };
  window.sessionStorage.setItem(`${storagePrefix}${id}`, JSON.stringify(queue));
  return id;
}

export function loadClassifierReviewQueue(
  id: string,
): ClassifierReviewQueue | null {
  try {
    const value = window.sessionStorage.getItem(`${storagePrefix}${id}`);
    if (!value) return null;
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    const record = parsed as Record<string, unknown>;
    if (
      !Array.isArray(record.mediaIds) ||
      !record.mediaIds.every((mediaId) => typeof mediaId === "string")
    ) {
      return null;
    }
    const mediaIds = record.mediaIds as string[];
    return {
      id,
      mediaIds,
      createdAt: typeof record.createdAt === "string" ? record.createdAt : "",
      sourceTotal:
        typeof record.sourceTotal === "number"
          ? record.sourceTotal
          : mediaIds.length,
      truncated: record.truncated === true,
    };
  } catch {
    return null;
  }
}
