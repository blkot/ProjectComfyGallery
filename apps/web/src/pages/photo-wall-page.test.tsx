import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router";

import { PhotoWallPage } from "./photo-wall-page";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", () => ({
  apiRequest: apiRequestMock,
}));

beforeEach(() => {
  apiRequestMock.mockImplementation((path: string) => {
    const request = new URL(path, "http://gallery.test");
    const offset = Number(request.searchParams.get("offset"));
    if (offset === 0) {
      return Promise.resolve({
        items: [
          wallImage("image-1", "one.png", 400, 200),
          wallImage("image-2", "two.png", 200, 400),
        ],
        total: 3,
        limit: 48,
        offset,
      });
    }
    return Promise.resolve({
      items: [wallImage("image-3", "three.png", 300, 300)],
      total: 3,
      limit: 48,
      offset,
    });
  });
});

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("PhotoWallPage", () => {
  it("loads only filtered images and appends the next batch on demand", async () => {
    renderPhotoWall(
      "/photo-wall?q=portrait&kind=video&favorite=true&return_to=%2Flibrary%3Fkind%3Dvideo",
    );

    expect(await screen.findByRole("img", { name: "one.png" })).toBeVisible();
    expect(screen.getByRole("img", { name: "two.png" })).toBeVisible();

    const firstRequest = new URL(
      apiRequestMock.mock.calls[0]?.[0] as string,
      "http://gallery.test",
    );
    expect(firstRequest.searchParams.get("kind")).toBe("image");
    expect(firstRequest.searchParams.get("q")).toBe("portrait");
    expect(firstRequest.searchParams.get("favorite")).toBe("true");
    expect(firstRequest.searchParams.get("trash")).toBe("false");
    expect(firstRequest.searchParams.get("offset")).toBe("0");

    fireEvent.change(screen.getByRole("slider", { name: "Photo wall zoom" }), {
      target: { value: "1.5" },
    });
    expect(screen.getByText("1.5×")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Load more images" }));
    expect(await screen.findByRole("img", { name: "three.png" })).toBeVisible();
    await waitFor(() =>
      expect(
        apiRequestMock.mock.calls.some(
          ([path]) =>
            new URL(path as string, "http://gallery.test").searchParams.get(
              "offset",
            ) === "2",
        ),
      ).toBe(true),
    );
  });

  it("returns to the originating library filter", async () => {
    renderPhotoWall(
      "/photo-wall?kind=image&trash=false&return_to=%2Flibrary%3Fkind%3Dvideo%26offset%3D48",
    );

    const backLink = await screen.findByRole("link", { name: "← Library" });
    expect(backLink).toHaveAttribute("href", "/library?kind=video&offset=48");
  });

  it("validates the requested export row range", async () => {
    renderPhotoWall("/photo-wall?kind=image");

    await screen.findByRole("img", { name: "one.png" });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Export from row" }), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByRole("spinbutton", { name: "Export to row" }), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Export PNG" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Enter a valid row range.",
    );
  });
});

function renderPhotoWall(initialEntry: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <PhotoWallPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function wallImage(
  id: string,
  original_filename: string,
  width: number,
  height: number,
) {
  return {
    id,
    kind: "image" as const,
    status: "ready",
    width,
    height,
    original_filename,
    preview_url: `/api/v1/media/${id}/preview`,
  };
}
