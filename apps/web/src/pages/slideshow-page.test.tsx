import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { SlideshowPage } from "./slideshow-page";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  apiRequest: apiRequestMock,
}));

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  apiRequestMock.mockResolvedValue({
    items: [
      {
        id: "image-1",
        kind: "image",
        status: "ready",
        original_filename: "one.png",
        width: 100,
        height: 100,
        duration_seconds: null,
        preview_url: "/api/v1/media/image-1/preview",
        playback_url: "/api/v1/media/image-1/playback",
      },
      {
        id: "video-1",
        kind: "video",
        status: "ready",
        original_filename: "two.mp4",
        width: 1920,
        height: 1080,
        duration_seconds: 10,
        preview_url: "/api/v1/media/video-1/preview",
        playback_url: "/api/v1/media/video-1/playback",
      },
    ],
    total: 2,
    limit: 2000,
    truncated: false,
    shuffle: true,
    random_seed: 42,
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  apiRequestMock.mockReset();
  cleanup();
});

describe("SlideshowPage", () => {
  it("advances images on the interval and videos when playback ends", async () => {
    const timeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const view = renderSlideshow(
      "/slideshow?source=filter&kind=image&shuffle=true&random_seed=42&interval=5&return_to=%2Flibrary%3Fkind%3Dimage",
    );

    expect(await screen.findByText("one.png")).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/v1/media/slideshow?kind=image&shuffle=true&random_seed=42&limit=2000",
    );

    const advanceImage = timeoutSpy.mock.calls.find(
      ([, delay]) => delay === 5_000,
    )?.[0];
    expect(advanceImage).toBeTypeOf("function");
    act(() => (advanceImage as () => void)());
    expect(screen.getByText("two.mp4")).toBeInTheDocument();

    const video = view.container.querySelector("video.slideshow-media");
    expect(video).not.toBeNull();
    fireEvent.ended(video as HTMLVideoElement);
    expect(screen.getByText("one.png")).toBeInTheDocument();
  });

  it("pauses and resumes hands-off playback", async () => {
    renderSlideshow("/slideshow?source=filter&interval=5");
    expect(await screen.findByText("one.png")).toBeInTheDocument();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    act(() => vi.advanceTimersByTime(10_000));
    expect(screen.getByText("one.png")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resume" }));
    act(() => vi.advanceTimersByTime(5_000));
    expect(screen.getByText("two.mp4")).toBeInTheDocument();
  });
});

function renderSlideshow(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <SlideshowPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
