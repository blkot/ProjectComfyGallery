import { describe, expect, it } from "vitest";

import { buildPhotoWallRows } from "./photo-wall";

describe("photo wall layout", () => {
  it("packs fixed-width images without horizontal gaps and centers shorter images by row height", () => {
    const first = { id: "first", width: 400, height: 200 };
    const second = { id: "second", width: 200, height: 400 };
    const third = { id: "third", width: 300, height: 300 };

    const rows = buildPhotoWallRows([first, second, third], 220, 100);

    expect(rows).toHaveLength(2);
    expect(rows[0]?.items.map((entry) => entry.item.id)).toEqual([
      "first",
      "second",
    ]);
    expect(rows[0]?.width).toBe(200);
    expect(rows[0]?.height).toBe(200);
    expect(rows[1]?.items[0]?.item.id).toBe("third");
    expect(rows[1]?.items[0]?.width).toBe(100);
    expect(rows[1]?.items[0]?.height).toBe(100);
  });

  it("clamps oversized images to the available wall width", () => {
    const rows = buildPhotoWallRows(
      [{ id: "wide", width: 1600, height: 900 }],
      240,
      800,
    );

    expect(rows[0]?.items[0]?.width).toBe(240);
    expect(rows[0]?.items[0]?.height).toBe(135);
  });
});
