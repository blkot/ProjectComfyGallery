import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MediaVariant } from "../lib/api";
import { SpatialVariantAttachment } from "./spatial-variant-attachment";

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

describe("SpatialVariantAttachment", () => {
  it("is available only for videos and explains atomic replacement", () => {
    const image = renderAttachment({ kind: "image" });
    expect(
      screen.queryByRole("button", { name: "Attach variant" }),
    ).not.toBeInTheDocument();

    image.unmount();
    renderAttachment({ variants: [readyVariant] });
    fireEvent.click(screen.getByRole("button", { name: "Replace variant" }));

    expect(
      screen.getByRole("dialog", { name: "Replace the active spatial video" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/current variant stays active/i),
    ).toBeInTheDocument();
  });

  it("confirms the multipart upload, polls processing, and refreshes media caches", async () => {
    const uploadResponse = deferred<unknown>();
    const finalStatus = deferred<unknown>();
    let statusRequests = 0;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === "POST") return uploadResponse.promise;
      if (path.endsWith("/variant-imports/variant-1")) {
        statusRequests += 1;
        return statusRequests === 1
          ? Promise.resolve(importStatus("processing", "variant-1"))
          : finalStatus.promise;
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const { queryClient } = renderAttachment({
      createIdempotencyKey: () => "command-key-1",
      pollInterval: 10,
    });
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    openAndSelectFile();
    expect(screen.getByText("spatial.mov")).toBeInTheDocument();
    expect(screen.getByText("4 B")).toBeInTheDocument();
    expect(apiRequestMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Confirm upload" }));
    expect(screen.getByText("Uploading")).toBeInTheDocument();
    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledTimes(1));

    const [postPath, postInit] = apiRequestMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(postPath).toBe("/api/v1/media/media-1/variant-imports");
    expect(postInit.method).toBe("POST");
    expect(postInit.headers).toEqual({ "Idempotency-Key": "command-key-1" });
    const body = postInit.body as FormData;
    expect((body.get("file") as File).name).toBe("spatial.mov");
    expect(body.get("role")).toBe("spatial_video");
    expect(body.get("source_asset_sha256")).toBe("source-sha");
    expect(body.get("converter_name")).toBe(
      "ComfyGallery web manual upload",
    );
    expect(body.has("favorite")).toBe(false);
    expect(body.has("prefer_spatial_playback")).toBe(false);

    uploadResponse.resolve(acceptedResponse("variant-1"));
    expect(await screen.findByText("Processing")).toBeInTheDocument();
    await waitFor(() => expect(statusRequests).toBe(2));

    finalStatus.resolve(importStatus("ready", "variant-1"));
    expect(await screen.findByText("Spatial video ready")).toBeInTheDocument();
    await waitFor(() => {
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["media-detail", "media-1"],
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["media"] });
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["media-navigation"],
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["jobs"] });
    });
  });

  it("surfaces validation failures and retries with a new command key", async () => {
    let postCount = 0;
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        postCount += 1;
        return Promise.resolve(acceptedResponse(`variant-${postCount}`));
      }
      if (path.endsWith("/variant-imports/variant-1")) {
        return Promise.resolve(
          importStatus("failed", "variant-1", {
            last_error_code: "VARIANT_SPATIAL_METADATA_INVALID",
            last_error_message: "The upload does not contain spatial metadata.",
          }),
        );
      }
      if (path.endsWith("/variant-imports/variant-2")) {
        return Promise.resolve(importStatus("ready", "variant-2"));
      }
      throw new Error(`Unexpected request: ${path}`);
    });
    const keys = ["command-key-1", "command-key-2"];
    renderAttachment({
      createIdempotencyKey: () => keys.shift() ?? "unexpected-key",
      pollInterval: 10,
    });

    openAndSelectFile();
    fireEvent.click(screen.getByRole("button", { name: "Confirm upload" }));

    expect(
      await screen.findByText("Spatial video validation failed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /VARIANT_SPATIAL_METADATA_INVALID: The upload does not contain spatial metadata/,
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry upload" }));
    expect(await screen.findByText("Spatial video ready")).toBeInTheDocument();

    const postCalls = apiRequestMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(postCalls).toHaveLength(2);
    expect(postCalls[0]?.[1]?.headers).toEqual({
      "Idempotency-Key": "command-key-1",
    });
    expect(postCalls[1]?.[1]?.headers).toEqual({
      "Idempotency-Key": "command-key-2",
    });
  });
});

function renderAttachment({
  kind = "video",
  variants = [],
  createIdempotencyKey,
  pollInterval,
}: {
  kind?: "image" | "video";
  variants?: MediaVariant[];
  createIdempotencyKey?: () => string;
  pollInterval?: number;
} = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  const result = render(
    <QueryClientProvider client={queryClient}>
      <SpatialVariantAttachment
        media={{
          id: "media-1",
          kind,
          sha256: "source-sha",
          variants,
        }}
        createIdempotencyKey={createIdempotencyKey}
        pollInterval={pollInterval}
      />
    </QueryClientProvider>,
  );
  return { ...result, queryClient };
}

function openAndSelectFile() {
  fireEvent.click(screen.getByRole("button", { name: "Attach variant" }));
  const file = new File(["mvhe"], "spatial.mov", {
    type: "video/quicktime",
  });
  fireEvent.change(screen.getByLabelText("Spatial video file"), {
    target: { files: [file] },
  });
}

function acceptedResponse(variantId: string) {
  return {
    variant: importStatus("staging", variantId),
    job: {
      id: `job-${variantId}`,
      status: "queued",
    },
  };
}

function importStatus(
  status: "staging" | "processing" | "ready" | "failed",
  id: string,
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    media_id: "media-1",
    role: "spatial_video",
    status,
    is_active: status === "ready",
    original_filename: "spatial.mov",
    last_error_code: null,
    last_error_message: null,
    ...overrides,
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((next) => {
    resolve = next;
  });
  return { promise, resolve };
}

const readyVariant: MediaVariant = {
  id: "ready-variant",
  role: "spatial_video",
  status: "ready",
  mime_type: "video/quicktime",
  byte_size: 4,
  width: 1920,
  height: 1080,
  duration_seconds: 1,
  frame_rate: 30,
  container: "mov",
  video_codec: "hevc",
  audio_codec: "aac",
  converter_name: "ComfyUI",
  converter_version: null,
  ready_at: "2026-07-31T00:00:00Z",
  content_url: "/api/v1/media/media-1/variants/ready-variant/content",
};
