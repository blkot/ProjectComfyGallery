import type { PhotoWallLayoutItem, PhotoWallRow, PhotoWallSource } from "./photo-wall";

export const photoWallSummaryTargetWidth = 3840;

export type PhotoWallExportSource = PhotoWallSource & {
  preview_url: string;
  status?: string;
};

export function selectPhotoWallRows<T>(
  rows: readonly PhotoWallRow<T>[],
  fromRow: number,
  toRow: number,
): PhotoWallRow<T>[] {
  if (
    !Number.isFinite(fromRow) ||
    !Number.isFinite(toRow) ||
    fromRow < 1 ||
    toRow < fromRow
  ) {
    return [];
  }

  return rows.slice(Math.floor(fromRow) - 1, Math.floor(toRow));
}

export async function renderPhotoWallSummary<
  T extends PhotoWallExportSource,
>(
  rows: readonly PhotoWallRow<T>[],
  targetWidth = photoWallSummaryTargetWidth,
): Promise<Blob> {
  if (rows.length === 0) {
    throw new Error("Select at least one photo wall row.");
  }

  const sourceWidth = Math.max(...rows.map((row) => row.width), 1);
  const outputWidth = Math.max(1, Math.round(targetWidth));
  const scale = outputWidth / sourceWidth;
  const sourceHeight = rows.reduce((sum, row) => sum + row.height, 0);
  const outputHeight = Math.max(1, Math.round(sourceHeight * scale));

  if (outputWidth > 32_767 || outputHeight > 32_767) {
    throw new Error(
      "The selected rows are too tall for one PNG. Export a smaller row range.",
    );
  }

  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext("2d");
  if (!context) {
    throw new Error("The browser could not create a 2D canvas.");
  }

  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";

  let rowTop = 0;
  for (const row of rows) {
    const exportableItems = row.items.filter(({ item }) =>
      isExportablePhotoWallItem(item),
    );
    const loadedImages = await Promise.all(
      exportableItems.map(async (item) => ({
        image: await loadPhotoWallImage(item),
        item,
      })),
    );
    const loadedByItem = new Map(
      loadedImages.map(({ image, item }) => [item, image]),
    );
    let itemLeft = 0;
    for (const item of row.items) {
      const image = loadedByItem.get(item);
      if (!image) {
        itemLeft += item.width;
        continue;
      }
      const top = rowTop + (row.height - item.height) / 2;
      context.drawImage(
        image,
        Math.round(itemLeft * scale),
        Math.round(top * scale),
        Math.max(1, Math.round(item.width * scale)),
        Math.max(1, Math.round(item.height * scale)),
      );
      itemLeft += item.width;
    }
    rowTop += row.height;
  }

  return canvasToBlob(canvas);
}

function isExportablePhotoWallItem<T extends PhotoWallExportSource>(
  item: T,
): boolean {
  return (
    item.status === undefined ||
    item.status === "ready" ||
    item.status === "ready_with_warnings"
  );
}

async function loadPhotoWallImage<T extends PhotoWallExportSource>(
  item: PhotoWallLayoutItem<T>,
): Promise<HTMLImageElement> {
  const image = new Image();
  image.decoding = "async";
  return new Promise((resolve, reject) => {
    image.onload = () => resolve(image);
    image.onerror = () =>
      reject(new Error(`Could not load preview for ${item.item.preview_url}.`));
    image.src = item.item.preview_url;
  });
}

function canvasToBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("The browser could not encode the summary PNG."));
      }
    }, "image/png");
  });
}
