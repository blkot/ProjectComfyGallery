import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RefObject } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

import type { MediaDetail } from "../lib/api";
import { MediaDetailPage } from "./media-detail-page";

const { apiRequestMock, favoriteClickMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  favoriteClickMock: vi.fn(),
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
  MediaFavoriteButton: ({
    buttonRef,
  }: {
    buttonRef?: RefObject<HTMLButtonElement | null>;
  }) => (
    <button
      ref={buttonRef}
      type="button"
      onClick={favoriteClickMock}
    >
      Favorite
    </button>
  ),
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
  favoriteClickMock.mockReset();
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
      if (path.startsWith("/api/v1/media/media-1/workflow-inputs")) {
        return Promise.resolve(emptyWorkflowInputs);
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
      if (path.startsWith("/api/v1/media/media-1/workflow-inputs")) {
        return Promise.resolve(emptyWorkflowInputs);
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
      if (path.startsWith("/api/v1/media/media-1/workflow-inputs")) {
        return Promise.resolve(emptyWorkflowInputs);
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

describe("MediaDetailPage keyboard controls", () => {
  it("navigates from a focused video, toggles playback, and toggles Favorite", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1") {
        return Promise.resolve(videoDetail);
      }
      if (path === "/api/v1/media/media-2") {
        return Promise.resolve({ ...videoDetail, id: "media-2" });
      }
      if (path.startsWith("/api/v1/media/media-1/navigation?")) {
        return Promise.resolve({
          media_id: "media-1",
          position: 1,
          total: 2,
          previous_id: null,
          previous_position: null,
          next_id: "media-2",
          next_position: 2,
        });
      }
      if (path.startsWith("/api/v1/media/media-2/navigation?")) {
        return Promise.resolve({
          media_id: "media-2",
          position: 2,
          total: 2,
          previous_id: "media-1",
          previous_position: 1,
          next_id: null,
          next_position: null,
        });
      }
      if (path.startsWith("/api/v1/media/media-1/workflow-inputs")) {
        return Promise.resolve(emptyWorkflowInputs);
      }
      if (path.startsWith("/api/v1/media/media-2/workflow-inputs")) {
        return Promise.resolve(emptyWorkflowInputs);
      }
      if (path.startsWith("/api/v1/media/media-")) {
        return Promise.resolve({});
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const playMock = vi
      .spyOn(HTMLMediaElement.prototype, "play")
      .mockResolvedValue(undefined);
    const pauseMock = vi
      .spyOn(HTMLMediaElement.prototype, "pause")
      .mockImplementation(() => {});

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/library/media-1"]}>
          <Routes>
            <Route
              path="/library/:mediaId"
              element={
                <>
                  <MediaDetailPage />
                  <LocationProbe />
                </>
              }
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const video = await waitFor(() => {
      const element = document.querySelector("video");
      if (!element) throw new Error("Video did not render");
      return element as HTMLVideoElement;
    });
    Object.defineProperty(video, "paused", {
      configurable: true,
      value: true,
    });
    video.focus();
    fireEvent.keyDown(video, { code: "Space", key: " " });
    expect(playMock).toHaveBeenCalledTimes(1);

    Object.defineProperty(video, "paused", {
      configurable: true,
      value: false,
    });
    fireEvent.keyDown(video, { code: "Space", key: " " });
    expect(pauseMock).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(video, { key: "f" });
    expect(favoriteClickMock).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(video, { key: "ArrowRight" });
    await waitFor(() =>
      expect(screen.getByTestId("media-location")).toHaveTextContent(
        "/library/media-2",
      ),
    );
  });
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="media-location">{location.pathname}</output>;
}

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

const emptyWorkflowInputs = {
  media_id: "media-1",
  items: [],
  total: 0,
  ready_count: 0,
  unresolved_count: 0,
};
