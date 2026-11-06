import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect, useState } from "react";
import { createMemoryRouter, Link, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MediaNavigation } from "./api";
import type { MediaBrowseKind } from "./media-browse";
import { useMediaOverlay } from "./use-media-overlay";

const { apiRequestMock } = vi.hoisted(() => ({ apiRequestMock: vi.fn() }));
vi.mock("./api", async () => ({
  ...await vi.importActual<typeof import("./api")>("./api"),
  apiRequest: apiRequestMock,
}));

const cleanupFunctions: Array<() => void> = [];
afterEach(() => {
  cleanup();
  cleanupFunctions.splice(0).forEach((dispose) => dispose());
  apiRequestMock.mockReset();
});

function Harness({ kind, onMount }: { kind: MediaBrowseKind; onMount: () => void }) {
  const overlay = useMediaOverlay(kind);
  const [draft, setDraft] = useState("");
  useEffect(onMount, [onMount]);
  return <section data-testid="source-page">
    <label>Source local draft<input value={draft} onChange={(event) => setDraft(event.target.value)} /></label>
    <button onClick={() => overlay.open("a")}>Open a</button>
    <output data-testid="restoring">{String(overlay.restoring)}</output>
    <output data-testid="notice">{overlay.notice}</output>
    {overlay.restoreError ? <div role="alert">{overlay.restoreError}<button onClick={overlay.retryRestore}>Retry</button></div> : null}
    {overlay.mediaId ? <div role="dialog" aria-label="Media overlay">
      <output data-testid="current-media">{overlay.mediaId}</output>
      <output data-testid="position">{overlay.navigation.data?.position ?? "loading"}</output>
      <button onClick={() => overlay.seek("b")}>Seek b</button>
      <button onClick={overlay.close}>Close overlay</button>
      <Link to={overlay.fullDetailHref}>Full detail</Link>
      <Link to={overlay.slideshowHref}>Slideshow</Link>
      <Link to={overlay.civitaiHref}>Civitai</Link>
    </div> : null}
  </section>;
}

function setup(kind: MediaBrowseKind, href: string) {
  const onMount = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const router = createMemoryRouter([
    { path: "/before", element: <p>Earlier page</p> },
    { path: kind === "library" ? "/library" : "/registries/prompts", element: <Harness kind={kind} onMount={onMount} /> },
    { path: "/library/:mediaId", element: <p>Full detail destination</p> },
    { path: "/library/:mediaId/civitai-post", element: <p>Civitai destination</p> },
    { path: "/slideshow", element: <p>Slideshow destination</p> },
  ], { initialEntries: ["/before", href], initialIndex: 1 });
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  cleanupFunctions.push(() => { router.dispose(); client.clear(); });
  return { router, client, onMount };
}

function navigation(id: string, position: number, previous: string | null = null, next: string | null = null): MediaNavigation {
  return { media_id: id, position, total: 100, previous_id: previous, previous_position: previous ? position - 1 : null, next_id: next, next_position: next ? position + 1 : null };
}

function mockApi(options: {
  navigation?: (id: string) => MediaNavigation | Promise<MediaNavigation>;
  page?: (offset: number) => { ids: string[]; total: number };
} = {}) {
  const defaultNavigation = (id: string) => id === "a"
    ? navigation("a", 48, "before-a", "b")
    : id === "b" ? navigation("b", 49, "a", "c") : navigation(id, 50, "b", "after-c");
  apiRequestMock.mockImplementation(async (path: string) => {
    const url = new URL(path, "http://gallery.local");
    if (url.pathname.endsWith("/navigation")) {
      const id = url.pathname.startsWith("/api/v1/media/") ? url.pathname.split("/")[4] : url.searchParams.get("media_id")!;
      return (options.navigation ?? defaultNavigation)(id);
    }
    if (url.pathname === "/api/v1/media" || url.pathname === "/api/v1/prompt-registry/lookup") {
      const offset = Number(url.searchParams.get("offset"));
      const page = options.page?.(offset) ?? {
        ids: offset === 0
          ? [...Array.from({ length: 47 }, (_, index) => `previous-${index}`), "a"]
          : ["b", "c", ...Array.from({ length: 46 }, (_, index) => `next-${index}`)],
        total: 100,
      };
      const items = page.ids.map((id) => ({ id, original_filename: `${id}.png`, favorite: true, content_rating: "sfw", is_trash: false, character_lora: "Alice" }));
      return url.pathname === "/api/v1/media"
        ? { items, total: page.total, offset, limit: 48 }
        : { prompt_id: url.searchParams.get("prompt_id"), source: "source", index: "12", entry: null, media: items, total_media: page.total, offset, limit: 48 };
    }
    throw new Error(`Unexpected request ${path}`);
  });
}

function params(router: ReturnType<typeof setup>["router"]) {
  return new URLSearchParams(router.state.location.search);
}

async function openAndSeek() {
  fireEvent.click(screen.getByRole("button", { name: "Open a" }));
  await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent(/^48$/));
  fireEvent.click(screen.getByRole("button", { name: "Seek b" }));
  await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent("49"));
}

async function expectRestored(router: ReturnType<typeof setup>["router"], id: string) {
  await waitFor(() => expect(params(router).get("return_media")).toBe(id));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByTestId("restoring")).toHaveTextContent("false");
}

describe("useMediaOverlay source-page integration", () => {
  it("pushes once, replaces on seek, and Back closes onto the last Library page without remounting its source", async () => {
    mockApi();
    const { router, onMount } = setup("library", "/library?q=portrait&favorite=true&content_rating=nsfw&trash=false&lora_reference_id=alice&lora_reference_id=bob&offset=0");
    const source = screen.getByTestId("source-page");
    fireEvent.change(screen.getByLabelText("Source local draft"), { target: { value: "keep this state" } });
    fireEvent.click(screen.getByRole("button", { name: "Open a" }));
    expect(router.state.historyAction).toBe("PUSH");
    await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent(/^48$/));
    fireEvent.click(screen.getByRole("button", { name: "Seek b" }));
    expect(router.state.historyAction).toBe("REPLACE");
    await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent("49"));

    await act(async () => { await router.navigate(-1); });
    await expectRestored(router, "b");

    expect(params(router).get("offset")).toBe("48");
    expect(params(router).get("q")).toBe("portrait");
    expect(params(router).get("favorite")).toBe("true");
    expect(params(router).get("content_rating")).toBe("nsfw");
    expect(params(router).get("trash")).toBe("false");
    expect(params(router).getAll("lora_reference_id")).toEqual(["alice", "bob"]);
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(screen.getByLabelText("Source local draft")).toHaveValue("keep this state");
    expect(onMount).toHaveBeenCalledTimes(1);
    const navigationCalls = apiRequestMock.mock.calls.map(([path]) => new URL(path, "http://gallery.local")).filter((url) => url.pathname.endsWith("/navigation"));
    expect(navigationCalls.every((url) => url.searchParams.get("favorite") === "true" && !url.searchParams.has("offset"))).toBe(true);
    await act(async () => { await router.navigate(-1); });
    expect(screen.getByText("Earlier page")).toBeInTheDocument();
  });

  it("uses the close button like Back for an owned overlay, without leaving stale overlay history entries", async () => {
    mockApi();
    const { router, onMount } = setup("library", "/library?favorite=true");
    const source = screen.getByTestId("source-page");
    await openAndSeek();
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await expectRestored(router, "b");
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(onMount).toHaveBeenCalledTimes(1);
    await act(async () => { await router.navigate(-1); });
    expect(screen.getByText("Earlier page")).toBeInTheDocument();
  });

  it("closes a refreshed deep link in place instead of popping to a previous external page", async () => {
    mockApi();
    const { router, onMount } = setup("library", "/library?favorite=true&offset=0&view_media=b&return_to=https%3A%2F%2Fevil.example");
    const source = screen.getByTestId("source-page");
    await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent("49"));
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await expectRestored(router, "b");
    expect(router.state.location.pathname).toBe("/library");
    expect(params(router).get("offset")).toBe("48");
    expect(params(router).has("return_to")).toBe(false);
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(onMount).toHaveBeenCalledTimes(1);
    await act(async () => { await router.navigate(-1); });
    expect(screen.getByText("Earlier page")).toBeInTheDocument();
  });

  it("retains the Registry prompt, character scope and heatmap UI while restoring a cross-page usage card", async () => {
    mockApi();
    const href = "/registries/prompts?prompt_id=source-00012&preferred_character_lora=Alice&character_lora=Alice&heatmap_source=source&heatmap_character=Bob&heatmap_not_faved=true&usage_offset=0";
    const { router, onMount } = setup("prompt", href);
    const source = screen.getByTestId("source-page");
    fireEvent.change(screen.getByLabelText("Source local draft"), { target: { value: "registry remains mounted" } });
    await openAndSeek();
    const fullDetail = new URL(screen.getByRole("link", { name: "Full detail" }).getAttribute("href")!, "http://gallery.local");
    const fullReturn = new URL(fullDetail.searchParams.get("return_to")!, "http://gallery.local");
    expect(fullReturn.pathname).toBe("/registries/prompts");
    expect(fullReturn.searchParams.get("usage_offset")).toBe("48");
    expect(fullReturn.searchParams.get("return_media")).toBe("b");
    for (const name of ["Slideshow", "Civitai"]) {
      const destination = new URL(screen.getByRole("link", { name }).getAttribute("href")!, "http://gallery.local");
      const returnTo = new URL(destination.searchParams.get("return_to")!, "http://gallery.local");
      expect(returnTo.pathname).toBe("/registries/prompts");
      expect(returnTo.searchParams.get("prompt_id")).toBe("source-00012");
      expect(returnTo.searchParams.get("preferred_character_lora")).toBe("Alice");
      expect(returnTo.searchParams.get("heatmap_character")).toBe("Bob");
      expect(returnTo.searchParams.get("view_media")).toBe("b");
    }
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await expectRestored(router, "b");
    expect(router.state.location.pathname).toBe("/registries/prompts");
    expect(params(router).get("usage_offset")).toBe("48");
    expect(params(router).get("prompt_id")).toBe("source-00012");
    expect(params(router).get("preferred_character_lora")).toBe("Alice");
    expect(params(router).get("character_lora")).toBe("Alice");
    expect(params(router).get("heatmap_character")).toBe("Bob");
    expect(params(router).get("heatmap_not_faved")).toBe("true");
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(screen.getByLabelText("Source local draft")).toHaveValue("registry remains mounted");
    expect(onMount).toHaveBeenCalledTimes(1);
    const requests = apiRequestMock.mock.calls.map(([path]) => new URL(path, "http://gallery.local"));
    expect(requests.every((url) => url.pathname.startsWith("/api/v1/prompt-registry/"))).toBe(true);
    expect(requests.every((url) => url.searchParams.get("prompt_id") === "source-00012" && url.searchParams.get("character_lora") === "Alice")).toBe(true);
    expect(requests.filter((url) => url.pathname.endsWith("/lookup")).every((url) => url.searchParams.get("group_by_character") === "true")).toBe(true);
  });

  it("restores the next in-scope neighbor if a mutation removes the current media from the filter", async () => {
    let removed = false;
    mockApi({ navigation: (id) => {
      if (id === "b" && removed) throw Object.assign(new Error("Media is outside this filter"), { status: 404 });
      if (id === "a") return navigation("a", 48, "before-a", "b");
      if (id === "b") return navigation("b", 49, "a", "c");
      return navigation("c", 49, "a", null);
    } });
    const { router } = setup("library", "/library?favorite=true&trash=false");
    const source = screen.getByTestId("source-page");
    await openAndSeek();
    removed = true;
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await expectRestored(router, "c");
    expect(params(router).get("favorite")).toBe("true");
    expect(params(router).get("offset")).toBe("48");
    expect(screen.getByTestId("notice")).toHaveTextContent("no longer matches");
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(apiRequestMock.mock.calls.some(([path]) => path.startsWith("/api/v1/media/c/navigation?") && path.includes("favorite=true"))).toBe(true);
  });

  it("clamps an emptied last page to the remaining last page when no old neighbor survives", async () => {
    let removed = false;
    mockApi({
      navigation: (id) => {
        if (removed) throw Object.assign(new Error("Media is outside this filter"), { status: 404 });
        return { ...navigation(id, 49, "removed-neighbor"), total: 49 };
      },
      page: (offset) => removed
        ? { ids: offset === 0 ? ["survivor"] : [], total: 1 }
        : { ids: offset === 48 ? ["b"] : ["survivor"], total: 49 },
    });
    const { router, client } = setup("library", "/library?favorite=true&offset=48&view_media=b");
    const source = screen.getByTestId("source-page");
    await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent("49"));
    await waitFor(() => expect(client.getQueryCache().findAll({ queryKey: ["media"] }).some((query) => query.state.status === "success")).toBe(true));
    removed = true;
    await client.invalidateQueries({ queryKey: ["media"], refetchType: "none" });
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await expectRestored(router, "survivor");
    expect(params(router).get("offset")).toBe("0");
    expect(params(router).get("favorite")).toBe("true");
    expect(screen.getByTestId("source-page")).toBe(source);
  });

  it("keeps the source visible after a transient restore failure and retries without widening the scope", async () => {
    let failRestore = false;
    mockApi({ navigation: (id) => {
      if (failRestore) throw Object.assign(new Error("Temporary network failure"), { status: 503 });
      return id === "a" ? navigation("a", 48, "before-a", "b") : navigation("b", 49, "a", "c");
    } });
    const { router, onMount } = setup("library", "/library?favorite=true&content_rating=nsfw");
    const source = screen.getByTestId("source-page");
    await openAndSeek();
    failRestore = true;
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not locate the last media"));
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(router.state.location.pathname).toBe("/library");
    expect(params(router).get("favorite")).toBe("true");
    expect(params(router).get("content_rating")).toBe("nsfw");
    failRestore = false;
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await expectRestored(router, "b");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(onMount).toHaveBeenCalledTimes(1);
  });

  it("returns an entirely emptied scope to page one without inventing an anchor", async () => {
    let removed = false;
    mockApi({
      navigation: (id) => {
        if (removed) throw Object.assign(new Error("Outside scope"), { status: 404 });
        return { ...navigation(id, 49, "also-removed"), total: 49 };
      },
      page: () => ({ ids: removed ? [] : ["b"], total: removed ? 0 : 49 }),
    });
    const { router } = setup("prompt", "/registries/prompts?prompt_id=source-12&character_lora=Alice&usage_offset=48&view_media=b");
    const source = screen.getByTestId("source-page");
    await waitFor(() => expect(screen.getByTestId("position")).toHaveTextContent("49"));
    removed = true;
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await waitFor(() => expect(params(router).get("usage_offset")).toBe("0"));
    expect(params(router).has("return_media")).toBe(false);
    expect(params(router).get("character_lora")).toBe("Alice");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByTestId("source-page")).toBe(source);
  });

  it.each([
    ["library", "/library?favorite=true", "/library?q=new-selection&favorite=false"],
    ["prompt", "/registries/prompts?prompt_id=source-12&character_lora=Alice", "/registries/prompts?prompt_id=source-13&character_lora=Bob"],
  ] as const)("does not overwrite a newer %s source selection when an old restore resolves late", async (kind, initialHref, nextHref) => {
    let delayRestore = false;
    let resolveNavigation!: (value: MediaNavigation) => void;
    const pendingNavigation = new Promise<MediaNavigation>((resolve) => { resolveNavigation = resolve; });
    mockApi({ navigation: (id) => {
      if (delayRestore) return pendingNavigation;
      return id === "a" ? navigation("a", 48, "before-a", "b") : navigation("b", 49, "a", "c");
    } });
    const { router, onMount } = setup(kind, initialHref);
    const source = screen.getByTestId("source-page");
    await openAndSeek();
    delayRestore = true;
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await waitFor(() => expect(screen.getByTestId("restoring")).toHaveTextContent("true"));

    await act(async () => { await router.navigate(nextHref); });
    await act(async () => {
      resolveNavigation(navigation("b", 49, "a", "c"));
      await pendingNavigation;
    });

    expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(nextHref);
    expect(screen.getByTestId("restoring")).toHaveTextContent("false");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByTestId("source-page")).toBe(source);
    expect(onMount).toHaveBeenCalledTimes(1);
  });

  it("removes a failed restore's retry action after the user changes the source scope", async () => {
    let failRestore = false;
    mockApi({ navigation: (id) => {
      if (failRestore) throw Object.assign(new Error("Temporary failure"), { status: 503 });
      return id === "a" ? navigation("a", 48, "before-a", "b") : navigation("b", 49, "a", "c");
    } });
    const { router } = setup("prompt", "/registries/prompts?prompt_id=source-12");
    const source = screen.getByTestId("source-page");
    await openAndSeek();
    failRestore = true;
    fireEvent.click(screen.getByRole("button", { name: "Close overlay" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument());

    await act(async () => { await router.navigate("/registries/prompts?prompt_id=source-13"); });

    expect(params(router).get("prompt_id")).toBe("source-13");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(screen.getByTestId("restoring")).toHaveTextContent("false");
    expect(screen.getByTestId("source-page")).toBe(source);
  });
});
