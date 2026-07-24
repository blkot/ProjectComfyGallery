import { describe, expect, it } from "vitest";

import {
  defaultMediaSort,
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
      "kind=image&checkpoint_reference_id=checkpoint&lora_reference_id=lora&sort=filename_asc&offset=48",
    );
    const href = mediaDetailHref("next-media", context, 97);
    const parsed = new URL(href, "http://example.test");

    expect(parsed.pathname).toBe("/library/next-media");
    expect(parsed.searchParams.get("checkpoint_reference_id")).toBe("checkpoint");
    expect(parsed.searchParams.get("lora_reference_id")).toBe("lora");
    expect(parsed.searchParams.get("sort")).toBe("filename_asc");
    expect(parsed.searchParams.get("offset")).toBe("96");
    expect(parsed.searchParams.get("limit")).toBe("48");
  });

  it("uses filters and sort for navigation while omitting page boundaries", () => {
    const context = new URLSearchParams("kind=video&sort=size_desc&offset=96&limit=48");
    const navigation = mediaNavigationQuery(context);
    const library = new URL(mediaLibraryHref(context), "http://example.test");

    expect(navigation.toString()).toBe("kind=video&sort=size_desc");
    expect(library.pathname).toBe("/library");
    expect(library.searchParams.get("offset")).toBe("96");
    expect(library.searchParams.has("limit")).toBe(false);
  });
});
