import { describe, expect, it } from "vitest";

import {
  browseDetailHref,
  browseNavigationPath,
  browsePageQuery,
  browseReturnHref,
  browseScope,
  browseSlideshowHref,
  overlayHref,
  safeBrowseHref,
} from "./media-browse";

function parse(href: string) {
  return new URL(href, "http://gallery.local");
}

describe("media browse URLs", () => {
  it("keeps Library navigation filtered while removing overlay and pagination state", () => {
    const search = new URLSearchParams("q=portrait&favorite=true&content_rating=nsfw&trash=false&lora_reference_id=alice&lora_reference_id=bob&offset=96&limit=48&view_media=a&return_media=old&panel=info");
    const scope = browseScope("library", search);
    expect(scope.get("q")).toBe("portrait");
    expect(scope.get("favorite")).toBe("true");
    expect(scope.get("content_rating")).toBe("nsfw");
    expect(scope.get("trash")).toBe("false");
    expect(scope.getAll("lora_reference_id")).toEqual(["alice", "bob"]);
    expect(scope.get("sort")).toBe("file_created_desc");
    for (const key of ["offset", "limit", "view_media", "return_media", "panel"]) {
      expect(scope.has(key)).toBe(false);
    }
    expect(parse(browseNavigationPath("library", "a", scope)).pathname).toBe("/api/v1/media/a/navigation");
    expect(search.get("view_media")).toBe("a");
  });

  it("preserves prompt usage character scope and group ordering without leaking heatmap filters", () => {
    const search = new URLSearchParams("prompt_id=source-00012&preferred_character_lora=Alice&character_lora=Alice&heatmap_source=source&heatmap_character=Bob&heatmap_not_faved=true&usage_offset=96&view_media=a");
    expect(Object.fromEntries(browseScope("prompt", search))).toEqual({
      prompt_id: "source-00012", preferred_character_lora: "Alice", character_lora: "Alice",
    });
    const navigation = parse(browseNavigationPath("prompt", "a", browseScope("prompt", search)));
    expect(navigation.pathname).toBe("/api/v1/prompt-registry/usage/navigation");
    expect(navigation.searchParams.get("media_id")).toBe("a");
    const page = browsePageQuery("prompt", search, 49);
    expect(Object.fromEntries(page)).toEqual({
      prompt_id: "source-00012", preferred_character_lora: "Alice", character_lora: "Alice",
      group_by_character: "true", limit: "48", offset: "48",
    });
  });

  it.each([[1, "0"], [48, "0"], [49, "48"], [96, "48"], [97, "96"]])(
    "restores one-based media position %i to offset %s",
    (position, offset) => {
      for (const kind of ["library", "prompt"] as const) {
        const search = new URLSearchParams("prompt_id=source-12&favorite=true&view_media=a&return_to=%2Flibrary&limit=48&panel=info");
        const returned = parse(browseReturnHref(kind, search, "last", position));
        expect(returned.pathname).toBe(kind === "library" ? "/library" : "/registries/prompts");
        expect(returned.searchParams.get(kind === "library" ? "offset" : "usage_offset")).toBe(offset);
        expect(returned.searchParams.get("return_media")).toBe("last");
        for (const key of ["view_media", "return_to", "limit", "panel"]) expect(returned.searchParams.has(key)).toBe(false);
      }
    },
  );

  it("keeps the current usage page when no absolute position is available", () => {
    const search = new URLSearchParams("prompt_id=source-12&usage_offset=96");
    expect(browsePageQuery("prompt", search).get("offset")).toBe("96");
    expect(parse(browseReturnHref("prompt", search, "last")).searchParams.get("usage_offset")).toBe("96");
  });

  it("builds full detail and action escapes that retain the Registry entry and heatmap state", () => {
    const search = new URLSearchParams("prompt_id=source-00012&preferred_character_lora=Alice&character_lora=Alice&heatmap_source=source&heatmap_character=Bob&usage_offset=0&view_media=last");
    const detail = parse(browseDetailHref("prompt", search, "last", 49));
    expect(detail.pathname).toBe("/library/last");
    const detailReturn = parse(detail.searchParams.get("return_to")!);
    expect(detailReturn.pathname).toBe("/registries/prompts");
    expect(detailReturn.searchParams.get("prompt_id")).toBe("source-00012");
    expect(detailReturn.searchParams.get("heatmap_character")).toBe("Bob");
    expect(detailReturn.searchParams.get("preferred_character_lora")).toBe("Alice");
    expect(detailReturn.searchParams.get("usage_offset")).toBe("48");
    expect(detailReturn.searchParams.get("return_media")).toBe("last");
    expect(detailReturn.searchParams.has("view_media")).toBe(false);

    const overlayReturn = overlayHref("/registries/prompts", search, "last");
    const slideshow = parse(browseSlideshowHref("prompt", search, "last", overlayReturn));
    expect(slideshow.pathname).toBe("/slideshow");
    expect(slideshow.searchParams.get("source")).toBe("prompt");
    expect(slideshow.searchParams.get("prompt_id")).toBe("source-00012");
    expect(slideshow.searchParams.get("character_lora")).toBe("Alice");
    expect(slideshow.searchParams.get("start_media")).toBe("last");
    expect(slideshow.searchParams.get("return_to")).toBe(overlayReturn);
    expect(slideshow.searchParams.has("heatmap_character")).toBe(false);
    expect(safeBrowseHref(overlayReturn)).toBe(overlayReturn);
  });

  it("retains a Library slideshow's active filters and return overlay", () => {
    const search = new URLSearchParams("q=portrait&favorite=true&trash=all&offset=48&view_media=last");
    const returnTo = overlayHref("/library", search, "last");
    const slideshow = parse(browseSlideshowHref("library", search, "last", returnTo));
    expect(slideshow.searchParams.get("source")).toBe("filter");
    expect(slideshow.searchParams.get("favorite")).toBe("true");
    expect(slideshow.searchParams.get("trash")).toBe("all");
    expect(slideshow.searchParams.get("q")).toBe("portrait");
    expect(slideshow.searchParams.get("return_to")).toBe(returnTo);
    expect(slideshow.searchParams.has("offset")).toBe(false);
    expect(slideshow.searchParams.has("view_media")).toBe(false);
  });

  it.each([
    null, "", "https://evil.example/library", "//evil.example/library", "/\\evil.example/library",
    "javascript:alert(1)", "/settings", "/library/a", "/registries", "/registries/prompts/extra",
    "/%2f%2fevil.example/library",
  ])("rejects an untrusted refresh/action return path: %s", (path) => {
    expect(safeBrowseHref(path)).toBeNull();
  });

  it("accepts only source-page paths and strips fragments", () => {
    expect(safeBrowseHref("/library?favorite=true&view_media=a#fragment")).toBe("/library?favorite=true&view_media=a");
    expect(safeBrowseHref("/registries/prompts?prompt_id=source-12&view_media=a")).toBe("/registries/prompts?prompt_id=source-12&view_media=a");
  });
});
