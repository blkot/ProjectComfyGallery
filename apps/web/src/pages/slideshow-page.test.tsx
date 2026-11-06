import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

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
  it("ignores malformed return URLs without crashing playback", async () => {
    renderSlideshow("/slideshow?return_to=%2F%5C%5B");
    expect(await screen.findByText("one.png")).toBeInTheDocument();
  });

  it("uses the prompt usage playlist and returns to its overlay at the last slide", async () => {
    function ReturnLocation() { const location = useLocation(); return <output data-testid="return-location">{location.pathname}{location.search}</output>; }
    const returnTo = "/registries/prompts?prompt_id=demo-7&preferred_character_lora=Alice&view_media=image-1";
    const params = new URLSearchParams({ source: "prompt", prompt_id: "demo-7", preferred_character_lora: "Alice", start_media: "image-1", return_to: returnTo });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/slideshow?${params}`]}>
      <Routes><Route path="/slideshow" element={<SlideshowPage />} /><Route path="/registries/prompts" element={<ReturnLocation />} /></Routes>
    </MemoryRouter></QueryClientProvider>);
    await screen.findByText("one.png");
    expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/prompt-registry/usage/slideshow?prompt_id=demo-7&preferred_character_lora=Alice&limit=2000&start_media_id=image-1");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Exit" }));
    const target = new URL((await screen.findByTestId("return-location")).textContent!, "http://gallery.test");
    expect(target.pathname).toBe("/registries/prompts");
    expect(target.searchParams.get("view_media")).toBe("video-1");
    expect(target.searchParams.get("preferred_character_lora")).toBe("Alice");
  });

  it("uses full-quality media for displayed and preloaded image slides", async () => {
    const secondImage = {
      id: "image-2",
      kind: "image",
      status: "ready",
      original_filename: "two.png",
      width: 200,
      height: 200,
      duration_seconds: null,
      preview_url: "/api/v1/media/image-2/preview",
      playback_url: "/api/v1/media/image-2/playback",
    };
    apiRequestMock.mockResolvedValueOnce({
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
        secondImage,
      ],
      total: 2,
      limit: 2000,
      truncated: false,
      shuffle: false,
      random_seed: null,
    });
    const imageSourceSetter = vi.spyOn(
      HTMLImageElement.prototype,
      "src",
      "set",
    );
    const view = renderSlideshow("/slideshow?source=filter&interval=5");

    expect(await screen.findByText("one.png")).toBeInTheDocument();
    expect(view.container.querySelector("img.slideshow-media")).toHaveAttribute(
      "src",
      "/api/v1/media/image-1/playback",
    );
    expect(imageSourceSetter).toHaveBeenCalledWith(secondImage.playback_url);
  });

  it("advances images on the interval and videos when playback ends", async () => {
    const timeoutSpy = vi.spyOn(globalThis, "setTimeout");
    const view = renderSlideshow(
      "/slideshow?source=filter&kind=image&shuffle=true&random_seed=42&interval=5&return_to=%2Flibrary%3Fkind%3Dimage",
    );

    expect(await screen.findByText("one.png")).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/v1/media/slideshow?kind=image&shuffle=true&random_seed=42&trash=false&limit=2000",
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

  it("starts at the requested media while keeping the playlist order", async () => {
    const view = renderSlideshow(
      "/slideshow?source=filter&start_media=video-1&interval=5&return_to=%2Freview%2Fsession-1%3Fposition%3D1",
    );

    expect(await screen.findByText("two.mp4")).toBeInTheDocument();
    expect(view.container.querySelector("video.slideshow-media")).not.toBeNull();
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/api/v1/media/slideshow?start_media_id=video-1&trash=false&limit=2000",
    );
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

  it("keeps audio enabled for video slides", async () => {
    const view = renderSlideshow("/slideshow?source=filter&interval=5");
    expect(await screen.findByText("one.png")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const video = view.container.querySelector("video.slideshow-media");
    expect(video).not.toBeNull();
    expect((video as HTMLVideoElement).muted).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Mute" }));
    expect((video as HTMLVideoElement).muted).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Enable sound" }));
    expect((video as HTMLVideoElement).muted).toBe(false);
  });

  it("moves to the previous and next items with wrapping controls", async () => {
    renderSlideshow("/slideshow?source=filter&interval=5");
    expect(await screen.findByText("one.png")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(screen.getByText("two.mp4")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("one.png")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
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
