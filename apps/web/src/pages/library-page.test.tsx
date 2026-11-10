import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { LibraryPage } from "./library-page";

const libraryStylesheet = readFileSync(
  resolve(process.cwd(), "src/styles.css"),
  "utf8",
);

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));
const requestFullscreenMock = vi.fn();

vi.mock("../lib/api", () => ({
  apiRequest: apiRequestMock,
}));

beforeEach(() => {
  requestFullscreenMock.mockReset().mockResolvedValue(undefined);
  Object.defineProperty(document.documentElement, "requestFullscreen", {
    configurable: true,
    value: requestFullscreenMock,
  });
  const values = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      get length() {
        return values.size;
      },
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      key: (index: number) => [...values.keys()][index] ?? null,
      removeItem: (key: string) => values.delete(key),
      setItem: (key: string, value: string) => values.set(key, value),
    } satisfies Storage,
  });
  apiRequestMock.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/media?")) {
      return Promise.resolve({
        items: [],
        total: 0,
        limit: 50,
        offset: 0,
      });
    }
    return Promise.resolve([]);
  });
});

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("LibraryPage controls sidebar", () => {
  it("collapses the controls and restores the saved preference", async () => {
    const first = renderLibrary("/library", { expandControls: false });
    const controls = screen.getByRole("complementary", {
      name: "Library controls",
    });
    const workspace = controls.closest(".library-workspace");
    const content = document.getElementById("library-controls-content");

    expect(workspace).toHaveAttribute("data-controls-collapsed", "true");
    expect(content).toHaveAttribute("hidden");

    fireEvent.click(
      screen.getByRole("button", { name: "Expand library controls" }),
    );

    expect(workspace).toHaveAttribute("data-controls-collapsed", "false");
    expect(content).not.toHaveAttribute("hidden");
    expect(
      screen.getByRole("button", { name: "Collapse library controls" }),
    ).toHaveAttribute("aria-expanded", "true");
    await waitFor(() =>
      expect(
        window.localStorage.getItem(
          "comfy-gallery.library-controls-collapsed-v2",
        ),
      ).toBe("false"),
    );

    first.unmount();
    renderLibrary();

    expect(
      screen
        .getByRole("complementary", { name: "Library controls" })
        .closest(".library-workspace"),
    ).toHaveAttribute("data-controls-collapsed", "false");
  });

  it("auto-collapses expanded controls after the pointer leaves", async () => {
    vi.useFakeTimers();
    try {
      renderLibrary("/library", { expandControls: false });
      const controls = screen.getByRole("complementary", {
        name: "Library controls",
      });
      const workspace = controls.closest(".library-workspace");

      fireEvent.click(
        screen.getByRole("button", { name: "Expand library controls" }),
      );
      expect(workspace).toHaveAttribute("data-controls-collapsed", "false");

      fireEvent.pointerLeave(controls);
      await act(async () => {
        vi.advanceTimersByTime(650);
      });

      expect(workspace).toHaveAttribute("data-controls-collapsed", "true");
    } finally {
      vi.useRealTimers();
    }
  });

  it("navigates with numbered pages around the current page", async () => {
    const mediaRequests: string[] = [];
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        mediaRequests.push(path);
        return Promise.resolve({
          items: [],
          total: 480,
          limit: 48,
          offset: Number(
            new URL(path, "http://gallery.test").searchParams.get("offset"),
          ),
        });
      }
      return Promise.resolve([]);
    });
    renderLibrary("/library?offset=192");

    const pagination = await screen.findByRole("navigation", {
      name: "Media pages above gallery",
    });
    expect(
      within(pagination).getByRole("button", { name: "Go to page 5" }),
    ).toHaveAttribute("aria-current", "page");

    fireEvent.click(
      within(pagination).getByRole("button", { name: "Go to page 6" }),
    );

    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            new URL(path, "http://gallery.test").searchParams.get("offset") ===
            "240",
        ),
      ).toBe(true),
    );
  });

  it("changes pages with the arrow keys without hijacking form controls", async () => {
    const mediaRequests: string[] = [];
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        mediaRequests.push(path);
        return Promise.resolve({
          items: [],
          total: 480,
          limit: 48,
          offset: Number(
            new URL(path, "http://gallery.test").searchParams.get("offset"),
          ),
        });
      }
      return Promise.resolve([]);
    });
    renderLibrary("/library?offset=48");

    await screen.findByRole("navigation", {
      name: "Media pages above gallery",
    });
    fireEvent.keyDown(window, { key: "ArrowRight" });

    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            new URL(path, "http://gallery.test").searchParams.get("offset") ===
            "96",
        ),
      ).toBe(true),
    );

    mediaRequests.length = 0;
    const pageInput = await screen.findByRole("spinbutton", {
      name: "Go to page from top pagination",
    });
    pageInput.focus();
    fireEvent.keyDown(pageInput, { key: "ArrowLeft" });
    expect(mediaRequests).toHaveLength(0);
  });

  it("excludes trash by default and supports explicit include or trash-only modes", async () => {
    const mediaRequests: string[] = [];
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        mediaRequests.push(path);
        return Promise.resolve({ items: [], total: 0, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });

    renderLibrary();

    const trashFilter = await screen.findByRole("radiogroup", {
      name: "Trash",
    });
    expect(
      within(trashFilter).getByRole("radio", { name: "Exclude" }),
    ).toBeChecked();
    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            new URL(path, "http://gallery.test").searchParams.get("trash") ===
            "false",
        ),
      ).toBe(true),
    );

    fireEvent.click(within(trashFilter).getByRole("radio", { name: "Include" }));
    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            !new URL(path, "http://gallery.test").searchParams.has("trash"),
        ),
      ).toBe(true),
    );

    fireEvent.click(within(trashFilter).getByRole("radio", { name: "Only" }));
    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            new URL(path, "http://gallery.test").searchParams.get("trash") ===
            "true",
        ),
      ).toBe(true),
    );
  });

  it("renders fixed filters as compact single-choice groups", async () => {
    renderLibrary(
      "/library?kind=video&favorite=true&prefer_spatial_playback=false&spatial_available=true",
    );

    expect(
      within(
        await screen.findByRole("radiogroup", { name: "Media type" }),
      ).getByRole("radio", { name: "Videos" }),
    ).toBeChecked();
    expect(
      within(screen.getByRole("radiogroup", { name: "Favorite" })).getByRole(
        "radio",
        { name: "Favorites" },
      ),
    ).toBeChecked();
    expect(
      within(
        screen.getByRole("radiogroup", { name: "Spatial preference" }),
      ).getByRole("radio", { name: "2D" }),
    ).toBeChecked();
    expect(
      within(screen.getByRole("radiogroup", { name: "Spatial video" })).getByRole(
        "radio",
        { name: "Ready" },
      ),
    ).toBeChecked();
    expect(
      within(screen.getByRole("radiogroup", { name: "Manual SFW / NSFW" })).getByRole(
        "radio",
        { name: "All" },
      ),
    ).toBeChecked();
  });

  it("passes the content safety filter through the media query", async () => {
    const mediaRequests: string[] = [];
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        mediaRequests.push(path);
        return Promise.resolve({ items: [], total: 0, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });

    renderLibrary();
    const filter = await screen.findByRole("radiogroup", {
      name: "Manual SFW / NSFW",
    });
    fireEvent.click(within(filter).getByRole("radio", { name: "NSFW" }));

    await waitFor(() =>
      expect(
        mediaRequests.some(
          (path) =>
            new URL(path, "http://gallery.test").searchParams.get(
              "content_rating",
            ) === "nsfw",
        ),
      ).toBe(true),
    );
  });

  it("submits and clears a URL-backed complete-library keyword", async () => {
    const mediaRequests: string[] = [];
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        mediaRequests.push(path);
        return Promise.resolve({ items: [], total: 0, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });
    renderLibrary(
      "/library?q=old+term&favorite=true&offset=96&return_media=previous",
    );

    const search = screen.getByRole("search", {
      name: "Search media library",
    });
    const input = within(search).getByRole("searchbox", {
      name: "Search entire library",
    });
    expect(input).toHaveValue("old term");

    fireEvent.change(input, { target: { value: "  new prompt  " } });
    fireEvent.click(within(search).getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(
        mediaRequests.some((path) => {
          const query = new URL(path, "http://gallery.test").searchParams;
          return (
            query.get("q") === "new prompt" &&
            query.get("favorite") === "true" &&
            query.get("offset") === "0" &&
            !query.has("return_media")
          );
        }),
      ).toBe(true),
    );
    expect(screen.getByRole("searchbox")).toHaveValue("new prompt");
    expect(
      await screen.findByText("No media matches “new prompt”"),
    ).toBeInTheDocument();

    fireEvent.click(within(search).getByRole("button", { name: "Clear" }));

    await waitFor(() =>
      expect(
        mediaRequests.some((path) => {
          const query = new URL(path, "http://gallery.test").searchParams;
          return !query.has("q") && query.get("favorite") === "true";
        }),
      ).toBe(true),
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("includes the active keyword in saved filter scopes", async () => {
    let savedPayload: { expression?: { q?: string | null } } | undefined;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [], total: 0, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/saved-filters" && init?.method === "POST") {
        savedPayload = JSON.parse(String(init.body)) as typeof savedPayload;
        return Promise.resolve({});
      }
      return Promise.resolve([]);
    });
    renderLibrary("/library?q=portrait&favorite=true");

    fireEvent.change(screen.getByLabelText("Saved filter name"), {
      target: { value: "Portrait search" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Save current filter" }),
    );

    await waitFor(() => expect(savedPayload?.expression?.q).toBe("portrait"));
  });

  it("offers filtered or collection slideshow sources", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [], total: 3, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/collections") {
        return Promise.resolve([
          {
            id: "collection-1",
            name: "Favorites reel",
            description: null,
            item_count: 2,
            created_at: "2026-08-02T00:00:00Z",
            updated_at: "2026-08-02T00:00:00Z",
          },
        ]);
      }
      return Promise.resolve([]);
    });
    renderLibrary("/library?kind=image");

    const photoWallLink = await screen.findByRole("link", {
      name: "Photo wall",
    });
    const photoWallUrl = new URL(
      photoWallLink.getAttribute("href") ?? "",
      "http://gallery.test",
    );
    expect(photoWallUrl.pathname).toBe("/photo-wall");
    expect(photoWallUrl.searchParams.get("kind")).toBe("image");

    const startButton = await screen.findByRole("button", {
      name: "Start slideshow",
    });
    await waitFor(() => expect(startButton).not.toBeDisabled());
    fireEvent.click(startButton);
    const dialog = screen.getByRole("dialog", { name: "Start slideshow" });
    expect(
      within(dialog).getByLabelText("Current filtered media (3)"),
    ).toBeChecked();
    expect(
      within(dialog).getByRole("radio", { name: "Collection" }),
    ).not.toBeDisabled();
    expect(
      within(dialog).getByRole("option", { name: "Favorites reel (2)" }),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByRole("checkbox", {
        name: "Shuffle this slideshow",
      }),
    ).not.toBeChecked();

    fireEvent.click(within(dialog).getByRole("button", { name: "Start" }));
    expect(requestFullscreenMock).not.toHaveBeenCalled();
  });

  it("keeps browse cards navigable and reveals selection controls only on demand", async () => {
    const item = mediaFixture({ id: "media-1", favorite: true });
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });

    renderLibrary();

    expect(await screen.findByText(item.original_filename)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Select media" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Remove from favorites" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Select media" }));

    expect(
      screen.getByRole("checkbox", { name: "Select media" }),
    ).toBeInTheDocument();
    expect(screen.getByTitle("Favorited")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove from favorites" }),
    ).toBeNull();

    fireEvent.click(
      screen.getByRole("button", { name: `Select ${item.original_filename}` }),
    );
    expect(screen.getByText("1 selected")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: `Deselect ${item.original_filename}` }),
    );
    expect(screen.getByText("Browse mode")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: "Select media" })).toBeNull();
  });

  it("sends selected favorite updates as one bulk action", async () => {
    const item = mediaFixture({ id: "media-2", favorite: false });
    let bulkPayload: Record<string, unknown> | undefined;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/media/bulk/favorite") {
        bulkPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return Promise.resolve({
          requested_count: 1,
          updated_count: 1,
          skipped_count: 0,
          errors: [],
        });
      }
      return Promise.resolve([]);
    });

    renderLibrary();
    await screen.findByText(item.original_filename);
    fireEvent.click(screen.getByRole("button", { name: "Select media" }));
    fireEvent.click(
      screen.getByRole("button", { name: `Select ${item.original_filename}` }),
    );
    fireEvent.click(screen.getByRole("button", { name: "★ Favorite" }));

    await waitFor(() => expect(bulkPayload?.favorite).toBe(true));
    expect(bulkPayload?.media_ids).toEqual([item.id]);
  });

  it("sends selected content rating updates as one bulk action", async () => {
    const item = mediaFixture({ id: "media-rating-1" });
    let bulkPayload: Record<string, unknown> | undefined;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/media/bulk/content-rating") {
        bulkPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return Promise.resolve({
          requested_count: 1,
          updated_count: 1,
          skipped_count: 0,
          errors: [],
        });
      }
      return Promise.resolve([]);
    });

    renderLibrary();
    await screen.findByText(item.original_filename);
    fireEvent.click(screen.getByRole("button", { name: "Select media" }));
    fireEvent.click(
      screen.getByRole("button", { name: `Select ${item.original_filename}` }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Mark NSFW" }));

    await waitFor(() => expect(bulkPayload?.content_rating).toBe("nsfw"));
    expect(bulkPayload?.media_ids).toEqual([item.id]);
  });

  it("renders a letter rating chip without workflow or warning badges", async () => {
    const item = mediaFixture({
      id: "media-card-badges",
      content_rating: "nsfw",
      warning_count: 2,
      workflow_status: "parsed",
      favorite: true,
    });
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });

    renderLibrary();

    const link = await screen.findByRole("link", { name: "Open media record" });
    const card = link.closest("article");
    expect(card).not.toBeNull();
    expect(
      within(card as HTMLElement).getByRole("img", {
        name: "Content rating: R",
      }),
    ).toHaveTextContent("R");
    expect(within(card as HTMLElement).queryByText(/WF/)).not.toBeInTheDocument();
    expect(within(card as HTMLElement).queryByText("Not started")).not.toBeInTheDocument();
    expect(
      within(card as HTMLElement).queryByText("Warning"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove from favorites" }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the rating badge in the action row beside the favorite badge", async () => {
    const item = mediaFixture({
      id: "media-card-badge-layout",
      content_rating: "nsfw",
      favorite: true,
    });
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      return Promise.resolve([]);
    });

    renderLibrary();

    const card = (await screen.findByRole("link", { name: "Open media record" }))
      .closest("article");
    expect(card).not.toBeNull();
    const actions = card?.querySelector(".media-card-actions");
    const rating = actions?.querySelector(".content-rating-badge");
    expect(actions).not.toBeNull();
    expect(rating).not.toBeNull();
    expect(libraryStylesheet).toMatch(
      /\.media-card-actions\s+\.content-rating-badge\s*\{[^}]*position:\s*static;/s,
    );
  });

  it("keeps filter selection exceptions in the bulk payload", async () => {
    const item = mediaFixture({ id: "media-3", favorite: false });
    let bulkPayload: Record<string, unknown> | undefined;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 3, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/media/bulk/favorite") {
        bulkPayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return Promise.resolve({
          requested_count: 2,
          updated_count: 2,
          skipped_count: 0,
          errors: [],
        });
      }
      return Promise.resolve([]);
    });

    renderLibrary("/library?q=portrait");
    await screen.findByText(item.original_filename);
    fireEvent.click(screen.getByRole("button", { name: "Select media" }));
    fireEvent.click(screen.getByRole("button", { name: "Select all 3 matching" }));
    fireEvent.click(
      screen.getByRole("button", { name: `Deselect ${item.original_filename}` }),
    );
    expect(screen.getByText("2 of 3 matching selected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "★ Favorite" }));

    await waitFor(() => expect(bulkPayload?.favorite).toBe(true));
    expect(bulkPayload?.exclude_media_ids).toEqual([item.id]);
    expect((bulkPayload?.filter as { q?: string }).q).toBe("portrait");
  });

  it("queues every image when classifying more matches than one request allows", async () => {
    const total = 3920;
    const mediaIds = Array.from({ length: total }, (_, index) => `character-${index}`);
    const classifierRequests: Array<Record<string, unknown>> = [];
    const idPageOffsets: number[] = [];
    const idPageCharacterLoras: Array<string | null> = [];
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        const url = new URL(path, "http://gallery.test");
        const offset = Number(url.searchParams.get("offset") ?? 0);
        const limit = Number(url.searchParams.get("limit") ?? 48);
        if (limit > 48) {
          idPageOffsets.push(offset);
          idPageCharacterLoras.push(url.searchParams.get("character_lora"));
        }
        return Promise.resolve({
          items: mediaIds.slice(offset, offset + limit).map((id) =>
            limit === 48 ? mediaFixture({ id, original_filename: `${id}.png` }) : { id },
          ),
          total,
          limit,
          offset,
          character_lora: "Alice",
        });
      }
      if (path === "/api/v1/media/bulk/nsfw-classification") {
        const payload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        classifierRequests.push(payload);
        const batchIds = payload.media_ids as string[];
        return Promise.resolve({
          requested_count: batchIds.length,
          queued_count: batchIds.length,
          reused_count: 0,
          skipped_count: 0,
          queue_failed_count: 0,
          job_ids: [],
        });
      }
      return Promise.resolve([]);
    });

    renderLibrary("/library?character_lora=Alice");
    await screen.findByText("character-0.png");
    fireEvent.click(screen.getByRole("button", { name: "Select media" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Select all 3920 matching" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "AI classify 3920 selected" }),
    );

    await waitFor(() => expect(classifierRequests).toHaveLength(2));
    expect(idPageOffsets).toEqual(Array.from({ length: 20 }, (_, index) => index * 200));
    expect(idPageCharacterLoras).toEqual(Array.from({ length: 20 }, () => "Alice"));
    const batches = classifierRequests.map((request) => request.media_ids as string[]);
    expect(batches.map((batch) => batch.length)).toEqual([2000, 1920]);
    expect(batches.flat()).toEqual(mediaIds);
    expect(classifierRequests.every((request) => request.force === true)).toBe(true);
    expect(await screen.findByText(/AI classification queued 3920/)).toBeInTheDocument();
  });

  it("queues one ZIP archive for the selected media and exposes its download link", async () => {
    const item = mediaFixture({ id: "media-archive-1", original_filename: "archive.png" });
    let archivePayload: Record<string, unknown> | undefined;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/api/v1/media?")) {
        return Promise.resolve({ items: [item], total: 1, limit: 48, offset: 0 });
      }
      if (path === "/api/v1/media/bulk/download") {
        archivePayload = JSON.parse(String(init?.body)) as Record<string, unknown>;
        return Promise.resolve({
          id: "archive-1",
          status: "queued",
          requested_count: 1,
          included_count: null,
          skipped_count: null,
          byte_size: null,
          sha256: null,
          error_code: null,
          error_message: null,
          created_at: "2026-01-01T00:00:00Z",
          started_at: null,
          completed_at: null,
          download_url: null,
        });
      }
      if (path === "/api/v1/media/bulk/download/archive-1") {
        return Promise.resolve({
          id: "archive-1",
          status: "succeeded",
          requested_count: 1,
          included_count: 1,
          skipped_count: 0,
          byte_size: 512,
          sha256: "a".repeat(64),
          error_code: null,
          error_message: null,
          created_at: "2026-01-01T00:00:00Z",
          started_at: "2026-01-01T00:00:01Z",
          completed_at: "2026-01-01T00:00:02Z",
          download_url: "/api/v1/media/bulk/download/archive-1/download",
        });
      }
      return Promise.resolve([]);
    });

    renderLibrary();
    await screen.findByText(item.original_filename);
    fireEvent.click(screen.getByRole("button", { name: "Select media" }));
    fireEvent.click(
      screen.getByRole("button", { name: `Select ${item.original_filename}` }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Download selected (1)" }));

    await waitFor(() =>
      expect(archivePayload?.media_ids).toEqual([item.id]),
    );
    expect(
      await screen.findByRole("link", { name: "Download ZIP" }),
    ).toHaveAttribute(
      "href",
      "/api/v1/media/bulk/download/archive-1/download",
    );
  });
});

function mediaFixture(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "media-fixture",
    kind: "image",
    status: "ready",
    detected_format: "png",
    mime_type: "image/png",
    width: 512,
    height: 512,
    duration_seconds: null,
    container: null,
    video_codec: null,
    warning_count: 0,
    byte_size: 1024,
    original_filename: "fixture.png",
    source_count: 1,
    workflow_status: "parsed",
    evaluation_state: "not_started",
    is_trash: false,
    spatial_available: false,
    prefer_spatial_playback: false,
    spatial_view_preferred: false,
    favorite: false,
    content_rating: "sfw",
    file_created_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    preview_url: "/api/v1/media/media-fixture/preview",
    ...overrides,
  };
}

function renderLibrary(
  initialEntry = "/library",
  { expandControls = true }: { expandControls?: boolean } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LibraryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  if (expandControls) {
    const expandButton = screen.queryByRole("button", {
      name: "Expand library controls",
    });
    if (expandButton) fireEvent.click(expandButton);
  }
  return result;
}
