import { describe, expect, it } from "vitest";

import {
  defaultMediaSort,
  libraryFilterExpression,
  mediaDetailHref,
  mediaLibraryHref,
  mediaListQuery,
  mediaNavigationQuery,
} from "./media-view";

describe("media view context", () => {
  it("normalizes the default sort and invalid offsets", () => {
    const result = mediaListQuery(new URLSearchParams("kind=image&offset=invalid"));

    expect(result.get("kind")).toBe("image");
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
    expect(parsed.searchParams.get("checkpoint_reference_id")).toBe("checkpoint");
    expect(parsed.searchParams.get("lora_reference_id")).toBe("lora");
    expect(parsed.searchParams.get("favorite")).toBe("true");
    expect(parsed.searchParams.get("spatial_view_preferred")).toBe("true");
    expect(parsed.searchParams.get("sort")).toBe("filename_asc");
    expect(parsed.searchParams.get("offset")).toBe("96");
    expect(parsed.searchParams.get("limit")).toBe("48");
  });

  it("uses filters and sort for navigation while omitting page boundaries", () => {
    const context = new URLSearchParams(
      "kind=video&sort=size_desc&offset=96&limit=48&panel=evaluation",
    );
    const navigation = mediaNavigationQuery(context);
    const library = new URL(mediaLibraryHref(context), "http://example.test");

    expect(navigation.toString()).toBe("kind=video&sort=size_desc");
    expect(library.pathname).toBe("/library");
    expect(library.searchParams.get("offset")).toBe("96");
    expect(library.searchParams.has("limit")).toBe(false);
    expect(library.searchParams.has("panel")).toBe(false);
  });

  it("preserves the active detail panel across previous and next media", () => {
    const href = mediaDetailHref(
      "next-media",
      new URLSearchParams("sort=file_created_desc&panel=evaluation"),
    );
    const parsed = new URL(href, "http://example.test");

    expect(parsed.searchParams.get("panel")).toBe("evaluation");
  });

  it("builds a reusable filter with multi-reference match semantics", () => {
    const expression = libraryFilterExpression(
      new URLSearchParams(
        "kind=image&trash=false&favorite=true&spatial_view_preferred=false&checkpoint_reference_id=checkpoint-a&checkpoint_reference_id=checkpoint-b&checkpoint_reference_match=any&lora_reference_id=lora-a&lora_reference_id=lora-b&lora_reference_match=all&sort=size_desc&offset=48",
      ),
    );

    expect(expression).toEqual({
      kind: "image",
      status: null,
      workflow_status: null,
      evaluation_state: null,
      trash: false,
      spatial_view_preferred: false,
      favorite: true,
      checkpoint_reference_ids: ["checkpoint-a", "checkpoint-b"],
      checkpoint_reference_match: "any",
      lora_reference_ids: ["lora-a", "lora-b"],
      lora_reference_match: "all",
    });
  });
});
