import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SpatialConversionPanel } from "./spatial-conversion-panel";

const { apiRequestMock } = vi.hoisted(() => ({ apiRequestMock: vi.fn() }));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, apiRequest: apiRequestMock };
});

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("SpatialConversionPanel", () => {
  it("starts a server-owned conversion and offers an on-demand refresh", async () => {
    let currentReads = 0;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/refresh") && init?.method === "POST") {
        return Promise.resolve(state("queued"));
      }
      if (init?.method === "POST") {
        return Promise.resolve(state("queued"));
      }
      if (path.endsWith("/spatial-conversions/current")) {
        currentReads += 1;
        if (currentReads === 1) return Promise.resolve(state(null));
        // The first read after the 202 still sees the pre-actor projection.
        // Refresh must keep observing briefly instead of treating it as final.
        return Promise.resolve(currentReads === 2 ? state("queued") : state("succeeded"));
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");
    render(
      <QueryClientProvider client={queryClient}>
        <SpatialConversionPanel mediaId="media-1" hasVariant={false} />
      </QueryClientProvider>,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Generate spatial video" }),
    );
    expect(await screen.findByText("Queued")).toBeInTheDocument();
    expect(screen.getByText(/runs independently/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh status" }));
    expect(await screen.findByText("Spatial video ready")).toBeInTheDocument();
    expect(currentReads).toBe(3);
    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/api/v1/spatial-conversions/run-1/refresh",
        { method: "POST" },
      );
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/api/v1/media/media-1/spatial-conversions",
        { method: "POST", body: "{}" },
      );
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["media-detail", "media-1"],
      });
    });
  });

  it("explains when MSS is not configured", async () => {
    apiRequestMock.mockResolvedValue({ configured: false, conversion: null, job: null });
    renderPanel();
    expect(await screen.findByText(/CG_MSS_BASE_URL/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate spatial video" })).toBeDisabled();
  });

  it("retries the durable job when a failed run is retryable", async () => {
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (path.endsWith("/spatial-conversions/current")) {
        return Promise.resolve(
          init ? state("queued") : failedState,
        );
      }
      if (path === "/api/v1/jobs/job-1/retry" && init?.method === "POST") {
        return Promise.resolve({ id: "job-1", status: "queued" });
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    renderPanel();

    fireEvent.click(
      await screen.findByRole("button", { name: "Retry spatial conversion" }),
    );
    await waitFor(() => {
      expect(apiRequestMock).toHaveBeenCalledWith(
        "/api/v1/jobs/job-1/retry",
        { method: "POST" },
      );
    });
  });
});

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <SpatialConversionPanel mediaId="media-1" hasVariant={false} />
    </QueryClientProvider>,
  );
}

function state(status: string | null) {
  return {
    configured: true,
    conversion: status
      ? {
          id: "run-1",
          media_id: "media-1",
          status,
          queue_position: status === "queued" ? 2 : null,
          error_code: null,
          error_message: null,
          last_reconciled_at:
            status === "succeeded" ? "2026-08-10T12:01:00Z" : null,
          updated_at:
            status === "succeeded" ? "2026-08-10T12:01:00Z" : "2026-08-10T12:00:00Z",
        }
      : null,
    job: null,
  };
}

const failedState = {
  configured: true,
  conversion: {
    id: "run-1",
    media_id: "media-1",
    status: "failed",
    queue_position: null,
    error_code: "MSS_STATUS_FAILED",
    error_message: "The status endpoint was unavailable.",
  },
  job: {
    id: "job-1",
    error_details: { retryable: true },
  },
};
