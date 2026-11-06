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

function openLocate() {
  fireEvent.click(screen.getByTestId("prompt-registry-locate-summary"));
}

beforeEach(() => {
  window.localStorage.clear();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  apiRequestMock.mockImplementation((path: string) => {
    if (path.startsWith("/api/v1/prompt-registry/sources")) {
      return Promise.resolve(["sfw-zimage-por-v3", "xanta-utils"]);
    }
    if (path.startsWith("/api/v1/prompt-registry/character-loras")) {
      return Promise.resolve([]);
    }
    if (path.startsWith("/api/v1/prompt-registry/heatmap")) {
      return Promise.resolve({
        items: [
          {
            prompt_id: "xanta-utils - 0007",
            source: "xanta-utils",
            index: "0007",
            media_count: 2,
          },
          {
            prompt_id: "xanta-utils - 0008",
            source: "xanta-utils",
            index: "0008",
            media_count: 0,
          },
        ],
        total: 2,
        limit: 20_000,
        offset: 0,
        max_media_count: 2,
      });
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
  vi.restoreAllMocks();
});

describe("PromptRegistryPage structured lookup", () => {
  it("seeks beside the resolved prompt without opening Locate and retains character context", async () => {
    renderPromptRegistry("/registries/prompts?prompt_id=xanta-utils%20-%200007&preferred_character_lora=Alice&character_lora=Alice&usage_offset=48&return_media=old-card");
    const next = await screen.findByRole("button", { name: "Next prompt index" });
    expect(screen.getByTestId("prompt-registry-locate")).not.toHaveAttribute("open");
    expect(next.closest(".prompt-registry-detail-header")).not.toBeNull();
    fireEvent.click(next);
    await waitFor(() => {
      const query = new URLSearchParams(screen.getByTestId("location-search").textContent ?? "");
      expect(query.get("prompt_id")).toBe("xanta-utils - 0008");
      expect(query.get("preferred_character_lora")).toBe("Alice");
      expect(query.get("character_lora")).toBe("Alice");
      expect(query.has("usage_offset")).toBe(false);
      expect(query.has("return_media")).toBe(false);
    });
  });

  it("disables the visible previous index control at zero", async () => {
    renderPromptRegistry("/registries/prompts?prompt_id=xanta-utils%20-%200000");
    expect(await screen.findByRole("button", { name: "Previous prompt index" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next prompt index" })).toBeEnabled();
  });

  it("uses registered sources as a select instead of requiring source text input", async () => {
    renderPromptRegistry();
    openLocate();

    const source = await screen.findByRole("combobox", { name: "Source" });
    await screen.findAllByRole("option", { name: "sfw-zimage-por-v3" });
    expect(source.tagName).toBe("SELECT");
    expect(screen.getAllByRole("option", { name: "sfw-zimage-por-v3" })).toHaveLength(2);
    expect(screen.getAllByRole("option", { name: "xanta-utils" })).toHaveLength(2);
    expect(
      apiRequestMock.mock.calls.some(([path]) => path === "/api/v1/prompt-registry/sources?limit=50"),
    ).toBe(true);
  });

  it("opens the prompt from a selected source and numeric index", async () => {
    renderPromptRegistry();
    openLocate();

    await screen.findAllByRole("option", { name: "sfw-zimage-por-v3" });
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

  it("loads the compact heatmap and resolves a clicked prompt square", async () => {
    renderPromptRegistry();

    const heatmap = await screen.findByTestId("prompt-registry-heatmap-canvas");
    expect(
      apiRequestMock.mock.calls.some(([path]) => path === "/api/v1/prompt-registry/heatmap?limit=20000"),
    ).toBe(true);

    fireEvent.click(heatmap, { clientX: 2, clientY: 22 });
    await waitFor(() => {
      const query = new URLSearchParams(screen.getByTestId("location-search").textContent ?? "");
      expect(query.get("prompt_id")).toBe("xanta-utils - 0007");
    });
  });

  it("groups prompt usage by character LoRA and prioritizes the heatmap selection", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/prompt-registry/sources")) {
        return Promise.resolve([]);
      }
      if (path.startsWith("/api/v1/prompt-registry/character-loras")) {
        return Promise.resolve([
          { name: "Character_A_v1", media_count: 2 },
          { name: "Character_B_v1", media_count: 1 },
        ]);
      }
      if (path.startsWith("/api/v1/prompt-registry/heatmap")) {
        return Promise.resolve({
          items: [
            {
              prompt_id: "xanta-utils - 0007",
              source: "xanta-utils",
              index: "0007",
              media_count: 2,
            },
          ],
          total: 1,
          limit: 20_000,
          offset: 0,
          max_media_count: 2,
        });
      }
      return Promise.resolve({
        prompt_id: "xanta-utils - 0007",
        source: "xanta-utils",
        index: "0007",
        entry: null,
        media: [
          {
            id: "m-b",
            kind: "image",
            original_filename: "character-b.png",
            width: 512,
            height: 768,
            duration_seconds: null,
            favorite: false,
            is_trash: false,
            character_lora: "Character_B_v1",
            content_rating: "sfw",
            preview_url: "/api/v1/media/m-b/preview",
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "m-none",
            kind: "image",
            original_filename: "undefined.png",
            width: 512,
            height: 768,
            duration_seconds: null,
            favorite: false,
            is_trash: false,
            character_lora: null,
            content_rating: "sfw",
            preview_url: "/api/v1/media/m-none/preview",
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: "m-a",
            kind: "image",
            original_filename: "character-a.png",
            width: 512,
            height: 768,
            duration_seconds: null,
            favorite: false,
            is_trash: false,
            character_lora: "Character_A_v1",
            content_rating: "sfw",
            preview_url: "/api/v1/media/m-a/preview",
            created_at: "2026-01-01T00:00:00Z",
          },
        ].sort((left, right) => (left.character_lora ?? "\uffff").localeCompare(right.character_lora ?? "\uffff")),
        total_media: 3,
        limit: 48,
        offset: 0,
      });
    });

    renderPromptRegistry();
    const character = await screen.findByRole("combobox", {
      name: "Heatmap character LoRA",
    });
    fireEvent.change(character, { target: { value: "Character_A_v1" } });
    const heatmap = await screen.findByTestId("prompt-registry-heatmap-canvas");
    fireEvent.click(heatmap, { clientX: 2, clientY: 22 });

    const groups = await screen.findByTestId("prompt-registry-usage-groups");
    expect(
      Array.from(groups.querySelectorAll("[data-testid^='prompt-registry-usage-group-']"))
        .map((group) => group.getAttribute("data-testid")),
    ).toEqual([
      "prompt-registry-usage-group-character_a_v1",
      "prompt-registry-usage-group-character_b_v1",
      "prompt-registry-usage-group-__undefined__",
    ]);
    expect(within(groups).getByRole("heading", { name: "Character_A_v1" })).toBeInTheDocument();
  });

  it("seeks the direct lookup index while preserving source and padding", async () => {
    renderPromptRegistry("/system/prompt-registry?prompt_id=xanta-utils%20-%200007");
    openLocate();

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
    const zeroView = renderPromptRegistry(
      "/system/prompt-registry?prompt_id=xanta-utils%20-%200000",
    );
    openLocate();
    expect(screen.getByRole("button", { name: "← Previous index" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next index →" })).toBeEnabled();
    zeroView.unmount();

    renderPromptRegistry("/system/prompt-registry?prompt_id=unstructured-id");
    openLocate();
    expect(screen.getByRole("button", { name: "← Previous index" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next index →" })).toBeDisabled();
  });

  it("scopes the heatmap to favorites by default and widens on request", async () => {
    renderPromptRegistry();

    await screen.findByTestId("prompt-registry-heatmap-canvas");
    expect(
      apiRequestMock.mock.calls.some(
        ([path]) => path === "/api/v1/prompt-registry/heatmap?limit=20000",
      ),
    ).toBe(true);

    fireEvent.click(screen.getByRole("checkbox", { name: "Include not-faved" }));
    await waitFor(() => {
      expect(
        apiRequestMock.mock.calls.some(
          ([path]) =>
            typeof path === "string" && path.includes("include_not_faved=true"),
        ),
      ).toBe(true);
    });

    fireEvent.click(screen.getByRole("checkbox", { name: "Include trash" }));
    await waitFor(() => {
      expect(
        apiRequestMock.mock.calls.some(
          ([path]) =>
            typeof path === "string" &&
            path.includes("include_not_faved=true") &&
            path.includes("include_trash=true"),
        ),
      ).toBe(true);
    });
  });

  it("restores persisted heatmap filters and remembers changes", async () => {
    window.localStorage.setItem(
      "comfy-gallery.prompt-heatmap.include-trash",
      "true",
    );
    renderPromptRegistry();

    await screen.findByTestId("prompt-registry-heatmap-canvas");
    expect(
      screen.getByRole("checkbox", { name: "Include trash" }),
    ).toBeChecked();
    expect(
      apiRequestMock.mock.calls.some(
        ([path]) =>
          typeof path === "string" && path.includes("include_trash=true"),
      ),
    ).toBe(true);

    fireEvent.click(
      screen.getByRole("checkbox", { name: "Include not-faved" }),
    );
    await waitFor(() => {
      expect(
        JSON.parse(
          window.localStorage.getItem(
            "comfy-gallery.prompt-heatmap.include-not-faved",
          ) ?? "null",
        ),
      ).toBe(true);
    });
  });

  it("restores a persisted character LoRA filter", async () => {
    window.localStorage.setItem(
      "comfy-gallery.prompt-heatmap.character-lora",
      JSON.stringify("Character_A_v1"),
    );
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/prompt-registry/character-loras")) {
        return Promise.resolve([{ name: "Character_A_v1", media_count: 2 }]);
      }
      if (path.startsWith("/api/v1/prompt-registry/sources")) {
        return Promise.resolve([]);
      }
      if (path.startsWith("/api/v1/prompt-registry/heatmap")) {
        return Promise.resolve({
          items: [],
          total: 0,
          limit: 20_000,
          offset: 0,
          max_media_count: 0,
        });
      }
      return Promise.resolve({});
    });

    renderPromptRegistry();

    const character = await screen.findByRole("combobox", {
      name: "Heatmap character LoRA",
    });
    await waitFor(() => expect(character).toHaveValue("Character_A_v1"));
    expect(
      apiRequestMock.mock.calls.some(
        ([path]) =>
          typeof path === "string" &&
          path.includes("character_lora=Character_A_v1"),
      ),
    ).toBe(true);
  });

  it("filters the heatmap by character LoRA", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/prompt-registry/character-loras")) {
        return Promise.resolve([
          { name: "Character_A_v1", media_count: 4 },
          { name: "Character_B_v1", media_count: 1 },
        ]);
      }
      if (path.startsWith("/api/v1/prompt-registry/sources")) {
        return Promise.resolve([]);
      }
      if (path.startsWith("/api/v1/prompt-registry/heatmap")) {
        return Promise.resolve({
          items: [],
          total: 0,
          limit: 20_000,
          offset: 0,
          max_media_count: 0,
        });
      }
      return Promise.resolve({});
    });

    renderPromptRegistry();

    const character = await screen.findByRole("combobox", {
      name: "Heatmap character LoRA",
    });
    await screen.findByRole("option", { name: /Character_A_v1/ });
    fireEvent.change(character, { target: { value: "Character_A_v1" } });

    await waitFor(() => {
      expect(
        apiRequestMock.mock.calls.some(
          ([path]) =>
            typeof path === "string" &&
            path.includes("character_lora=Character_A_v1"),
        ),
      ).toBe(true);
    });
  });

  it("marks trashed media and lets trash outrank favorite", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path.startsWith("/api/v1/prompt-registry/sources")) {
        return Promise.resolve([]);
      }
      if (path.startsWith("/api/v1/prompt-registry/character-loras")) {
        return Promise.resolve([]);
      }
      if (path.startsWith("/api/v1/prompt-registry/heatmap")) {
        return Promise.resolve({
          items: [],
          total: 0,
          limit: 20_000,
          offset: 0,
          max_media_count: 0,
        });
      }
      return Promise.resolve({
        prompt_id: "xanta-utils - 0007",
        source: "xanta-utils",
        index: "0007",
        entry: {
          id: "7f4b0b1e-1f7a-4c4b-8a0e-2b6f8f0a4d10",
          source: "xanta-utils",
          index: "0007",
          prompt: "A prompt",
          negative_prompt: null,
          metadata: {},
          origin: "manual",
          media_count: 1,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        },
        media: [
          {
            id: "m-1",
            kind: "image",
            original_filename: "trashed.png",
            width: 512,
            height: 768,
            duration_seconds: null,
            favorite: true,
            is_trash: true,
            character_lora: "Character_A_v1",
            content_rating: "sfw",
            preview_url: "/api/v1/media/m-1/preview",
            created_at: "2026-01-01T00:00:00Z",
          },
        ],
        total_media: 1,
        limit: 48,
        offset: 0,
      });
    });

    renderPromptRegistry("/system/prompt-registry?prompt_id=xanta-utils%20-%200007");

    const card = await screen.findByRole("link", { name: /trashed\.png/ });
    expect(card.className).toContain("is-trash");
    expect(within(card).getByText("Trash")).toBeInTheDocument();
    expect(within(card).queryByText(/favorite/)).not.toBeInTheDocument();
  });
});
