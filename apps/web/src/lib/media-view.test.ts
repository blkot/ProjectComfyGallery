import { describe, expect, it } from "vitest";

import {
  defaultMediaSort,
  libraryFilterExpression,
  mediaDetailHref,
  mediaLibraryHref,
  mediaListQuery,
  mediaNavigationQuery,
  pageOffsetForNumber,
  paginationItems,
  slideshowHref,
  slideshowPlaylistQuery,
} from "./media-view";

describe("media view context", () => {
  it("normalizes the default sort and invalid offsets", () => {
    const result = mediaListQuery(
      new URLSearchParams(
        "kind=image&offset=invalid&return_media=library-only-context",
      ),
    );

    expect(result.get("kind")).toBe("image");
    expect(result.has("return_media")).toBe(false);
    expect(result.get("offset")).toBe("0");
    expect(result.get("limit")).toBe("48");
    expect(result.get("sort")).toBe(defaultMediaSort);
  });

  it("preserves filters and moves the library offset with neighbor positions", () => {
    const context = new URLSearchParams(
      "kind=image&favorite=true&spatial_view_preferred=true&checkpoint_reference_id=checkpoint&lora_reference_id=lora&sort=filename_asc&offset=48",
    );
    const href = mediaDetailHref("next-media", context, 97);
    const parsed = new URL(href, "http://example.test");

    expect(parsed.pathname).toBe("/library/next-media");
    expect(parsed.searchParams.get("checkpoint_reference_id")).toBe(
      "checkpoint",
    );
    expect(parsed.searchParams.get("lora_reference_id")).toBe("lora");
    expect(parsed.searchParams.get("favorite")).toBe("true");
    expect(parsed.searchParams.get("prefer_spatial_playback")).toBe("true");
    expect(parsed.searchParams.has("spatial_view_preferred")).toBe(false);
    expect(parsed.searchParams.get("sort")).toBe("filename_asc");
    expect(parsed.searchParams.get("offset")).toBe("96");
    expect(parsed.searchParams.get("limit")).toBe("48");
    expect(parsed.searchParams.get("return_media")).toBe("next-media");
  });

  it("uses filters and sort for navigation while omitting page boundaries", () => {
    const context = new URLSearchParams(
      "kind=video&sort=size_desc&offset=96&limit=48&panel=evaluation&return_media=current-media",
    );
    const navigation = mediaNavigationQuery(context);
    const library = new URL(mediaLibraryHref(context), "http://example.test");

    expect(navigation.toString()).toBe("kind=video&sort=size_desc");
    expect(library.pathname).toBe("/library");
    expect(library.searchParams.get("offset")).toBe("96");
    expect(library.searchParams.has("limit")).toBe(false);
    expect(library.searchParams.has("panel")).toBe(false);
    expect(library.searchParams.get("return_media")).toBe("current-media");
  });

  it("preserves the active detail panel across previous and next media", () => {
    const href = mediaDetailHref(
      "next-media",
      new URLSearchParams("sort=file_created_desc&panel=evaluation"),
    );
    const parsed = new URL(href, "http://example.test");

    expect(parsed.searchParams.get("panel")).toBe("evaluation");
  });

  it("clamps direct page jumps to the available page range", () => {
    expect(pageOffsetForNumber(1, 240)).toBe(0);
    expect(pageOffsetForNumber(3, 240)).toBe(96);
    expect(pageOffsetForNumber(999, 240)).toBe(192);
    expect(pageOffsetForNumber(0, 240)).toBe(0);
    expect(pageOffsetForNumber(Number.NaN, 0)).toBe(0);
  });

  it("builds compact clickable page ranges around the current page", () => {
    expect(paginationItems(3, 5)).toEqual([1, 2, 3, 4, 5]);
    expect(paginationItems(10, 20)).toEqual([
      1,
      "start-ellipsis",
      8,
      9,
      10,
      11,
      12,
      "end-ellipsis",
      20,
    ]);
    expect(paginationItems(1, 20)).toEqual([
      1,
      2,
      3,
      4,
      5,
      6,
      "end-ellipsis",
      20,
    ]);
    expect(paginationItems(20, 20)).toEqual([
      1,
      "start-ellipsis",
      15,
      16,
      17,
      18,
      19,
      20,
    ]);
  });

  it("builds a reusable filter with multi-reference match semantics", () => {
    const expression = libraryFilterExpression(
      new URLSearchParams(
        "kind=image&trash=false&favorite=true&prefer_spatial_playback=false&spatial_available=true&checkpoint_reference_id=checkpoint-a&checkpoint_reference_id=checkpoint-b&checkpoint_reference_match=any&lora_reference_id=lora-a&lora_reference_id=lora-b&lora_reference_match=all&sort=size_desc&offset=48",
      ),
    );

    expect(expression).toEqual({
      kind: "image",
      status: null,
      workflow_status: null,
      evaluation_state: null,
      trash: false,
      prefer_spatial_playback: false,
      spatial_available: true,
      favorite: true,
      checkpoint_reference_ids: ["checkpoint-a", "checkpoint-b"],
      checkpoint_reference_match: "any",
      lora_reference_ids: ["lora-a", "lora-b"],
      lora_reference_match: "all",
    });
  });

  it("builds a filtered shuffled slideshow without page boundaries", () => {
    const href = slideshowHref(
      new URLSearchParams(
        "kind=video&favorite=true&offset=96&return_media=selected&sort=size_desc",
      ),
      {
        source: "filter",
        collectionId: "",
        shuffle: true,
        intervalSeconds: 12,
      },
    );
    const parsed = new URL(href, "http://example.test");
    const playlist = slideshowPlaylistQuery(parsed.searchParams);

    expect(parsed.pathname).toBe("/slideshow");
    expect(parsed.searchParams.get("return_to")).toContain("/library?");
    expect(parsed.searchParams.get("interval")).toBe("12");
    expect(Number(parsed.searchParams.get("random_seed"))).toBeGreaterThanOrEqual(
      0,
    );
    expect(playlist.get("kind")).toBe("video");
    expect(playlist.get("favorite")).toBe("true");
    expect(playlist.get("sort")).toBe("size_desc");
    expect(playlist.get("shuffle")).toBe("true");
    expect(playlist.get("limit")).toBe("2000");
    expect(playlist.has("offset")).toBe(false);
    expect(playlist.has("return_to")).toBe(false);
  });

  it("isolates collection slideshows from the current Library filters", () => {
    const href = slideshowHref(
      new URLSearchParams("kind=image&favorite=true"),
      {
        source: "collection",
        collectionId: "collection-1",
        shuffle: false,
        intervalSeconds: 8,
      },
    );
    const parsed = new URL(href, "http://example.test");
    const playlist = slideshowPlaylistQuery(parsed.searchParams);

    expect(playlist.get("collection_id")).toBe("collection-1");
    expect(playlist.get("shuffle")).toBe("false");
    expect(playlist.has("kind")).toBe(false);
    expect(playlist.has("favorite")).toBe(false);
    expect(playlist.has("random_seed")).toBe(false);
  });
});
