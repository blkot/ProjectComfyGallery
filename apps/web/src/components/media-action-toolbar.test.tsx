import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { createRef } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContentRating, MediaDetail } from "../lib/api";
import { MediaActionToolbar } from "./media-action-toolbar";

const { apiRequestMock } = vi.hoisted(() => ({ apiRequestMock: vi.fn() }));
vi.mock("../lib/api", async () => ({
  ...await vi.importActual<typeof import("../lib/api")>("../lib/api"),
  apiRequest: apiRequestMock,
}));

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

const media = {
  id: "one",
  favorite: false,
  content_rating: "sfw",
  prefer_spatial_playback: false,
  is_trash: false,
  original_url: "/api/v1/media/one/original?token=existing",
} as MediaDetail;

describe("MediaActionToolbar", () => {
  it("keeps compact icons accessible and links to original, slideshow and Civitai", () => {
    const client = new QueryClient();
    render(<QueryClientProvider client={client}><MemoryRouter>
      <MediaActionToolbar media={media} slideshowHref="/slideshow?start=one" civitaiHref="/library/one/civitai-post" />
    </MemoryRouter></QueryClientProvider>);

    expect(screen.getByRole("button", { name: "Add to favorites" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "SFW" })).toHaveTextContent("N");
    expect(screen.getByRole("button", { name: "NSFW" })).toHaveTextContent("R");
    expect(screen.getByRole("button", { name: "Prefer spatial playback when available" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("link", { name: "Download original" })).toHaveAttribute("href", "/api/v1/media/one/original?token=existing&download=true");
    expect(screen.getByRole("link", { name: "Start slideshow from here" })).toHaveAttribute("href", "/slideshow?start=one");
    expect(screen.getByRole("link", { name: "Post to Civitai" })).toHaveAttribute("href", "/library/one/civitai-post");
    expect(screen.getByRole("button", { name: "Move to Trash" })).toBeEnabled();
    client.clear();
  });

  it("points N at the opposite rating in both directions and forwards the favorite ref", async () => {
    const client = new QueryClient();
    const favoriteRef = createRef<HTMLButtonElement>();
    const ratingRef = createRef<HTMLButtonElement>();
    apiRequestMock.mockImplementation((_path: string, request: { body: string }) => Promise.resolve({
      media_id: "one", ...JSON.parse(request.body), updated_at: "now",
    }));
    const view = (rating: ContentRating) => <QueryClientProvider client={client}><MemoryRouter>
      <MediaActionToolbar media={{ ...media, content_rating: rating }} slideshowHref="/slideshow" civitaiHref="/civitai" favoriteButtonRef={favoriteRef} contentRatingShortcutRef={ratingRef} />
    </MemoryRouter></QueryClientProvider>;
    const { rerender } = render(view("sfw"));
    expect(favoriteRef.current).toBe(screen.getByRole("button", { name: "Add to favorites" }));
    expect(ratingRef.current).toBe(screen.getByRole("button", { name: "NSFW" }));
    await act(async () => ratingRef.current?.click());
    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/media/one/content-rating", { method: "PUT", body: '{"content_rating":"nsfw"}' }));
    rerender(view("nsfw"));
    expect(ratingRef.current).toBe(screen.getByRole("button", { name: "SFW" }));
    expect(ratingRef.current).toHaveAttribute("aria-keyshortcuts", "N");
    await waitFor(() => expect(ratingRef.current).toBeEnabled());
    await act(async () => ratingRef.current?.click());
    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/media/one/content-rating", { method: "PUT", body: '{"content_rating":"sfw"}' }));
    client.clear();
  });
});
