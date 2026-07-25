import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router";

import { AppShell } from "./app-shell";

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
});

afterEach(() => {
  cleanup();
});

describe("AppShell navigation", () => {
  it("collapses to icons and restores the saved preference", async () => {
    const first = renderShell();
    const shell = screen.getByText("Page content").closest(".app-shell");

    expect(shell).toHaveAttribute("data-sidebar-collapsed", "false");
    fireEvent.click(screen.getByRole("button", { name: "Collapse navigation" }));
    expect(shell).toHaveAttribute("data-sidebar-collapsed", "true");
    await waitFor(() =>
      expect(window.localStorage.getItem("comfy-gallery.sidebar-collapsed")).toBe(
        "true",
      ),
    );

    first.unmount();
    renderShell();
    expect(screen.getByText("Page content").closest(".app-shell")).toHaveAttribute(
      "data-sidebar-collapsed",
      "true",
    );
    expect(
      screen.getByRole("button", { name: "Expand navigation" }),
    ).toBeInTheDocument();
  });
});

function renderShell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/library"]}>
        <AppShell user={{ id: "user-id", username: "admin" }}>
          <div>Page content</div>
        </AppShell>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
