import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MediaTrashButton } from "./media-trash-button";

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

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("MediaTrashButton", () => {
  it("loads the evaluation identity on demand and moves media to Trash", async () => {
    const evaluation = {
      id: "evaluation-1",
      media_id: "media-1",
      evaluation_kind: "base",
      version: 3,
      is_trash: false,
      scores: [],
      criteria: [],
    };
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1/evaluation-context") {
        return Promise.resolve({
          media_id: "media-1",
          progress_state: "not_started",
          is_trash: false,
          enabled_modules: [],
          available_modules: [],
          prompts: [],
          evaluations: [evaluation],
        });
      }
      if (path === "/api/v1/evaluations/evaluation-1/trash") {
        return Promise.resolve({
          ...evaluation,
          version: 4,
          is_trash: true,
        });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(["media-detail", "media-1"], {
      id: "media-1",
      is_trash: false,
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MediaTrashButton mediaId="media-1" isTrash={false} />
      </QueryClientProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Move to Trash" }));

    await waitFor(() =>
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/api/v1/evaluations/evaluation-1/trash",
        {
          method: "POST",
          body: JSON.stringify({ expected_version: 3 }),
        },
      ),
    );
    expect(
      queryClient.getQueryData<{ is_trash: boolean }>([
        "media-detail",
        "media-1",
      ])?.is_trash,
    ).toBe(true);
  });
});
