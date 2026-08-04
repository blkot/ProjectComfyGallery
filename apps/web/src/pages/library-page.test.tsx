import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
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
    const first = renderLibrary();
    const controls = screen.getByRole("complementary", {
      name: "Library controls",
    });
    const workspace = controls.closest(".library-workspace");
    const content = document.getElementById("library-controls-content");

    expect(workspace).toHaveAttribute("data-controls-collapsed", "false");
    expect(content).not.toHaveAttribute("hidden");

    fireEvent.click(
      screen.getByRole("button", { name: "Collapse library controls" }),
    );

    expect(workspace).toHaveAttribute("data-controls-collapsed", "true");
    expect(content).toHaveAttribute("hidden");
    expect(
      screen.getByRole("button", { name: "Expand library controls" }),
    ).toHaveAttribute("aria-expanded", "false");
    await waitFor(() =>
      expect(
        window.localStorage.getItem(
          "comfy-gallery.library-controls-collapsed",
        ),
      ).toBe("true"),
    );

    first.unmount();
    renderLibrary();

    expect(
      screen
        .getByRole("complementary", { name: "Library controls" })
        .closest(".library-workspace"),
    ).toHaveAttribute("data-controls-collapsed", "true");
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
});

function renderLibrary(initialEntry = "/library") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <LibraryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
