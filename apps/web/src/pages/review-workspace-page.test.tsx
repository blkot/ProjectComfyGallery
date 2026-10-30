import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

import { ReviewWorkspacePage } from "./review-workspace-page";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, apiRequest: apiRequestMock };
});

vi.mock("../components/evaluation-controls", () => ({
  EvaluationSection: () => null,
}));

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("ReviewWorkspacePage slideshow action", () => {
  it("starts at the current media with the review session filter", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/review-sessions/session-1") {
        return Promise.resolve(reviewSession);
      }
      if (path.startsWith("/api/v1/review-sessions/session-1/items/")) {
        return Promise.resolve(reviewItem);
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    render(
      <QueryClientProvider
        client={
          new QueryClient({ defaultOptions: { queries: { retry: false } } })
        }
      >
        <MemoryRouter initialEntries={["/review/session-1?position=2"]}>
          <Routes>
            <Route
              path="/review/:sessionId"
              element={<ReviewWorkspacePage />}
            />
            <Route path="*" element={<LocationProbe />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", {
        name: "Start slideshow from here",
      }),
    );

    await waitFor(() => expect(screen.getByTestId("location")).toBeVisible());
    const location = new URL(
      screen.getByTestId("location").textContent ?? "",
      "http://example.test",
    );
    expect(location.pathname).toBe("/slideshow");
    expect(location.searchParams.get("start_media")).toBe("media-2");
    expect(location.searchParams.get("q")).toBe("portrait");
    expect(location.searchParams.get("kind")).toBe("image");
    expect(location.searchParams.get("trash")).toBe("false");
    expect(location.searchParams.get("return_to")).toBe(
      "/review/session-1?position=2",
    );
  });
});

function LocationProbe() {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}
      {location.search}
    </output>
  );
}

const reviewSession = {
  id: "session-1",
  name: null,
  source_kind: "filter",
  scope_snapshot: {
    source_kind: "filter",
    filter: {
      q: "portrait",
      kind: "image",
      trash: false,
    },
  },
  ordering_mode: "stable",
  random_seed: null,
  optional_modules: [],
  status: "active",
  current_cursor: 2,
  candidate_count: 5,
  progress_counts: { not_started: 4, in_progress: 1, complete: 0 },
  last_opened_at: "2026-10-13T00:00:00Z",
  created_at: "2026-10-13T00:00:00Z",
  updated_at: "2026-10-13T00:00:00Z",
};

const reviewItem = {
  session: reviewSession,
  position: 2,
  media: {
    id: "media-2",
    kind: "image",
    preview_url: "/api/v1/media/media-2/preview",
    playback_url: "/api/v1/media/media-2/playback",
    width: 100,
    height: 100,
    duration_seconds: null,
  },
  prompts: [],
  evaluations: [],
};
