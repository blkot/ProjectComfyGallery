import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import type { MediaDetail } from "../lib/api";
import { MediaDetailPage } from "./media-detail-page";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return {
    ...actual,
    apiRequest: apiRequestMock,
  };
});

vi.mock("../components/media-evaluation-panel", () => ({
  MediaEvaluationPanel: () => null,
}));

vi.mock("../components/media-favorite-button", () => ({
  MediaFavoriteButton: () => <button type="button">Favorite</button>,
}));

vi.mock("../components/media-spatial-preference-button", () => ({
  MediaSpatialPreferenceButton: () => (
    <button type="button">Spatial preference</button>
  ),
}));

vi.mock("../components/workflow-inspector", () => ({
  WorkflowInspector: () => <section>Workflow inspector</section>,
}));

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("MediaDetailPage spatial variant action", () => {
  it("keeps the video attachment action visible without opening storage details", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1") {
        return Promise.resolve(videoDetail);
      }
      if (path.startsWith("/api/v1/media/media-1/navigation?")) {
        return Promise.resolve({
          media_id: "media-1",
          position: 1,
          total: 1,
          previous_id: null,
          previous_position: null,
          next_id: null,
          next_position: null,
        });
      }
      if (path.startsWith("/api/v1/media/media-1/workflow?")) {
        return Promise.resolve({});
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/media/media-1"]}>
          <Routes>
            <Route path="/media/:mediaId" element={<MediaDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByRole("button", { name: "Attach variant" }),
    ).toBeVisible();
  });
});

describe("MediaDetailPage image viewer", () => {
  it("groups media actions in the viewer toolbar", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1") {
        return Promise.resolve(imageDetail);
      }
      if (path.startsWith("/api/v1/media/media-1/navigation?")) {
        return Promise.resolve({
          media_id: "media-1",
          position: 1,
          total: 1,
          previous_id: null,
          previous_position: null,
          next_id: null,
          next_position: null,
        });
      }
      if (path.startsWith("/api/v1/media/media-1/workflow?")) {
        return Promise.resolve({});
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const view = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/media/media-1"]}>
          <Routes>
            <Route path="/media/:mediaId" element={<MediaDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("original.png")).toBeInTheDocument();
    const toolbar = view.container.querySelector(".media-record-toolbar");
    expect(toolbar).not.toBeNull();
    const actions = within(toolbar as HTMLElement);
    expect(
      actions.getByRole("button", { name: "Favorite" }),
    ).toBeInTheDocument();
    expect(
      actions.getByRole("button", { name: "Spatial preference" }),
    ).toBeInTheDocument();
    expect(actions.getByRole("link", { name: "Download" })).toBeInTheDocument();
    expect(
      actions.getByRole("button", { name: "Move to Trash" }),
    ).toBeInTheDocument();
    expect(actions.queryByRole("button", { name: /delete/i })).toBeNull();
  });

  it("renders the immutable original instead of the generated preview", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1") {
        return Promise.resolve(imageDetail);
      }
      if (path.startsWith("/api/v1/media/media-1/navigation?")) {
        return Promise.resolve({
          media_id: "media-1",
          position: 1,
          total: 1,
          previous_id: null,
          previous_position: null,
          next_id: null,
          next_position: null,
        });
      }
      if (path.startsWith("/api/v1/media/media-1/workflow?")) {
        return Promise.resolve({});
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/media/media-1"]}>
          <Routes>
            <Route path="/media/:mediaId" element={<MediaDetailPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const image = await screen.findByRole("img", { name: "original.png" });
    expect(image).toHaveAttribute("src", "/original-image");
    expect(image).not.toHaveAttribute("src", "/preview-image");
  });
});

const videoDetail: MediaDetail = {
  id: "media-1",
  kind: "video",
  status: "ready",
  detected_format: "quicktime",
  mime_type: "video/quicktime",
  width: 1920,
  height: 1080,
  duration_seconds: 5,
  container: "mov",
  video_codec: "hevc",
  warning_count: 0,
  byte_size: 1024,
  original_filename: "ordinary.mov",
  workflow_status: "ready",
  evaluation_state: "not_started",
  is_trash: false,
  spatial_available: false,
  prefer_spatial_playback: false,
  spatial_view_preferred: false,
  favorite: false,
  file_created_at: "2026-07-31T00:00:00Z",
  created_at: "2026-07-31T00:00:00Z",
  preview_url: "/preview",
  frame_rate: 30,
  audio_codec: "aac",
  probe_data: {},
  last_error_code: null,
  last_error_message: null,
  sha256: "source-sha",
  original_extension: ".mov",
  updated_at: "2026-07-31T00:00:00Z",
  playback_url: "/playback",
  original_url: "/original",
  workflow_url: "/workflow",
  derivatives: [],
  variants: [],
  sources: [],
};

const imageDetail: MediaDetail = {
  ...videoDetail,
  kind: "image",
  detected_format: "png",
  mime_type: "image/png",
  duration_seconds: null,
  container: null,
  video_codec: null,
  audio_codec: null,
  original_filename: "original.png",
  preview_url: "/preview-image",
  playback_url: "/playback-image",
  original_url: "/original-image",
};
