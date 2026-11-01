export type PhotoWallSource = {
  width: number | null;
  height: number | null;
};

export type PhotoWallLayoutItem<T> = {
  item: T;
  width: number;
  height: number;
};

export type PhotoWallRow<T> = {
  items: PhotoWallLayoutItem<T>[];
  width: number;
  height: number;
};

/**
 * Packs fixed-width images into gapless rows. Each row owns its tallest image
 * height so the renderer can center shorter images without stretching them.
 */
export function buildPhotoWallRows<T extends PhotoWallSource>(
  items: readonly T[],
  containerWidth: number,
  targetImageWidth: number,
): PhotoWallRow<T>[] {
  const safeContainerWidth = Math.max(
    1,
    Number.isFinite(containerWidth) ? containerWidth : targetImageWidth,
  );
  const safeTargetWidth = Math.max(
    1,
    Number.isFinite(targetImageWidth) ? targetImageWidth : 1,
  );
  const imageWidth = Math.min(safeTargetWidth, safeContainerWidth);
  const rows: PhotoWallRow<T>[] = [];
  let currentItems: PhotoWallLayoutItem<T>[] = [];
  let currentWidth = 0;
  let currentHeight = 0;

  const flushRow = () => {
    if (currentItems.length === 0) return;
    rows.push({
      items: currentItems,
      width: currentWidth,
      height: currentHeight,
    });
    currentItems = [];
    currentWidth = 0;
    currentHeight = 0;
  };

  for (const item of items) {
    const aspectRatio = validAspectRatio(item);
    const imageHeight = imageWidth / aspectRatio;

    if (
      currentItems.length > 0 &&
      currentWidth + imageWidth > safeContainerWidth
    ) {
      flushRow();
    }

    currentItems.push({
      item,
      width: imageWidth,
      height: imageHeight,
    });
    currentWidth += imageWidth;
    currentHeight = Math.max(currentHeight, imageHeight);
  }

  flushRow();
  return rows;
}

function validAspectRatio(item: PhotoWallSource): number {
  if (
    typeof item.width === "number" &&
    item.width > 0 &&
    typeof item.height === "number" &&
    item.height > 0
  ) {
    return item.width / item.height;
  }
  return 1;
}
