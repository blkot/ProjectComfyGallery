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

vi.mock("../lib/api", () => ({
  apiRequest: apiRequestMock,
}));

beforeEach(() => {
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
