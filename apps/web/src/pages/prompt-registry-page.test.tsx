import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, useLocation } from "react-router";

import { PromptRegistryPage } from "./prompt-registry-page";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  apiRequest: apiRequestMock,
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location-search">{location.search}</output>;
}

function renderPromptRegistry(initialEntry = "/system/prompt-registry") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PromptRegistryPage />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  apiRequestMock.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/prompt-registry/sources")) {
      return Promise.resolve(["sfw-zimage-por-v3", "xanta-utils"]);
    }
    return Promise.resolve({
      prompt_id: "xanta-utils - 0007",
      source: "xanta-utils",
      index: "0007",
      entry: null,
      media: [],
      total_media: 0,
      limit: 48,
      offset: 0,
    });
  });
});

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("PromptRegistryPage structured lookup", () => {
  it("uses registered sources as a select instead of requiring source text input", async () => {
    renderPromptRegistry();

    const source = await screen.findByRole("combobox", { name: "Source" });
    await screen.findByRole("option", { name: "sfw-zimage-por-v3" });
    expect(source.tagName).toBe("SELECT");
    expect(screen.getByRole("option", { name: "sfw-zimage-por-v3" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "xanta-utils" })).toBeInTheDocument();
    expect(
      apiRequestMock.mock.calls.some(([path]) => path === "/api/v1/prompt-registry/sources?limit=50"),
    ).toBe(true);
  });

  it("opens the prompt from a selected source and numeric index", async () => {
    renderPromptRegistry();

    await screen.findByRole("option", { name: "sfw-zimage-por-v3" });
    fireEvent.change(screen.getByRole("combobox", { name: "Source" }), {
      target: { value: "xanta-utils" },
    });
    fireEvent.change(screen.getByLabelText("Index"), {
      target: { value: "0007" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Open source + index" }));

    await waitFor(() => {
      const query = new URLSearchParams(
        screen.getByTestId("location-search").textContent ?? "",
      );
      expect(query.get("prompt_id")).toBe("xanta-utils - 0007");
    });
  });

  it("seeks the direct lookup index while preserving source and padding", async () => {
    renderPromptRegistry("/system/prompt-registry?prompt_id=xanta-utils%20-%200007");

    const previous = screen.getByRole("button", { name: "← Previous index" });
    const next = screen.getByRole("button", { name: "Next index →" });
    expect(previous).toBeEnabled();
    expect(next).toBeEnabled();

    fireEvent.click(previous);
    await waitFor(() => {
      const query = new URLSearchParams(
        screen.getByTestId("location-search").textContent ?? "",
      );
      expect(query.get("prompt_id")).toBe("xanta-utils - 0006");
    });

    fireEvent.click(next);
    await waitFor(() => {
      const query = new URLSearchParams(
        screen.getByTestId("location-search").textContent ?? "",
      );
      expect(query.get("prompt_id")).toBe("xanta-utils - 0007");
    });
  });

  it("disables previous navigation at zero and invalid prompt IDs", async () => {
    const zeroView = renderPromptRegistry("/system/prompt-registry?prompt_id=xanta-utils%20-%200000");
    expect(screen.getByRole("button", { name: "← Previous index" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next index →" })).toBeEnabled();
    zeroView.unmount();

    renderPromptRegistry("/system/prompt-registry?prompt_id=unstructured-id");
    expect(screen.getByRole("button", { name: "← Previous index" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next index →" })).toBeDisabled();
  });
});
