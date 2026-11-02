import { describe, expect, it } from "vitest";

import { selectPhotoWallRows } from "./photo-wall-export";

describe("photo wall export ranges", () => {
  it("selects an inclusive one-based row range", () => {
    const rows = makeRows(["row-1", "row-2", "row-3"]);

    expect(
      selectPhotoWallRows(rows, 2, 3).map((row) => row.items[0]?.item.id),
    ).toEqual(["row-2", "row-3"]);
  });

  it("returns no rows for an invalid range", () => {
    const rows = makeRows(["row-1"]);

    expect(selectPhotoWallRows(rows, 0, 1)).toEqual([]);
    expect(selectPhotoWallRows(rows, 2, 1)).toEqual([]);
  });
});

function makeRows(ids: string[]) {
  return ids.map((id) => ({
    items: [{ item: { id }, width: 1, height: 1 }],
    width: 1,
    height: 1,
  }));
}
