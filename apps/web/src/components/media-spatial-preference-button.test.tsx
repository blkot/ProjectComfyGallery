import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MediaSpatialPreferenceButton } from "./media-spatial-preference-button";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    apiRequest: vi.fn(),
  };
});

afterEach(cleanup);

describe("MediaSpatialPreferenceButton", () => {
  it("exposes separate standard and spatial styling states", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <MediaSpatialPreferenceButton mediaId="media-1" preferred={false} />
      </QueryClientProvider>,
    );

    expect(
      screen.getByRole("button", { name: "Prefer spatial playback when available" }),
    ).toHaveAttribute("data-preference", "standard");

    view.rerender(
      <QueryClientProvider client={queryClient}>
        <MediaSpatialPreferenceButton mediaId="media-1" preferred />
      </QueryClientProvider>,
    );
    const spatialButton = screen.getByRole("button", {
      name: "Use standard playback when possible",
    });
    expect(spatialButton).toHaveAttribute("data-preference", "spatial");
    expect(spatialButton).toHaveAttribute("aria-pressed", "true");
  });
});
