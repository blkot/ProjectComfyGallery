import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkflowInputList, WorkflowInputReference } from "../lib/api";
import { WorkflowInputMedia } from "./workflow-input-media";

const { apiRequestMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, apiRequest: apiRequestMock };
});

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
});

describe("WorkflowInputMedia", () => {
  it("renders captured previews, provenance, and retryable failures", async () => {
    apiRequestMock.mockImplementation((path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve({
          media_id: "media-1",
          job: { status: "queued" },
        });
      }
      if (path === "/api/v1/media/media-1/workflow-inputs") {
        return Promise.resolve(workflowInputs);
      }
      throw new Error(`Unexpected request: ${path}`);
    });

    renderInputMedia();

    expect(await screen.findByRole("img", { name: "Workflow input reference.png" }))
      .toHaveAttribute("src", "/api/v1/media/media-1/workflow-inputs/input-1/content");
    expect(document.querySelector("video")).toHaveAttribute(
      "src",
      "/api/v1/media/media-1/workflow-inputs/input-2/content",
    );
    expect(screen.getByText("Node 12 · LoadImage · image")).toBeInTheDocument();
    expect(screen.getAllByText("Missing from ComfyUI")).not.toHaveLength(0);
    expect(
      screen.getByText("WORKFLOW_INPUT_NOT_FOUND: ComfyUI no longer has this file."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry capture" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry capture" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Capture queued (Queued).",
    );
    await waitFor(() => {
      expect(
        apiRequestMock.mock.calls.some(
          ([path, init]) =>
            path === "/api/v1/media/media-1/workflow-inputs/resolve" &&
            (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true);
    });
  });

  it("explains when a workflow has no detected input media", async () => {
    apiRequestMock.mockResolvedValue({
      media_id: "media-1",
      items: [],
      total: 0,
      ready_count: 0,
      unresolved_count: 0,
    } satisfies WorkflowInputList);

    renderInputMedia();

    expect(
      await screen.findByText("No workflow input media detected"),
    ).toBeInTheDocument();
    expect(screen.getByText("0 ready · 0 detected")).toBeInTheDocument();
  });
});

function renderInputMedia() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <WorkflowInputMedia mediaId="media-1" />
    </QueryClientProvider>,
  );
}

function reference(
  overrides: Partial<WorkflowInputReference>,
): WorkflowInputReference {
  return {
    id: "input-1",
    status: "ready",
    representation: "api_prompt",
    original_node_id: "12",
    class_type: "LoadImage",
    locator: "inputs.image",
    input_name: "image",
    media_kind_hint: "image",
    source_filename: "reference.png",
    source_subfolder: "",
    source_type: "input",
    raw_value: "reference.png",
    attempt_count: 1,
    last_attempt_at: "2026-08-09T00:00:00Z",
    resolved_at: "2026-08-09T00:00:01Z",
    last_error_code: null,
    last_error_message: null,
    resolution_details: {},
    asset: {
      id: "asset-1",
      sha256: "a".repeat(64),
      kind: "image",
      detected_format: "png",
      mime_type: "image/png",
      byte_size: 4096,
      width: 1024,
      height: 768,
      duration_seconds: null,
      frame_rate: null,
      container: null,
      video_codec: null,
      audio_codec: null,
    },
    content_url: "/api/v1/media/media-1/workflow-inputs/input-1/content",
    ...overrides,
  };
}

const workflowInputs: WorkflowInputList = {
  media_id: "media-1",
  items: [
    reference({}),
    reference({
      id: "input-2",
      original_node_id: "18",
      class_type: "LoadVideo",
      input_name: "file",
      source_filename: "reference.mov",
      media_kind_hint: "video",
      asset: {
        ...reference({}).asset!,
        id: "asset-2",
        kind: "video",
        detected_format: "quicktime",
        mime_type: "video/quicktime",
        duration_seconds: 2.5,
        width: 1920,
        height: 1080,
      },
      content_url:
        "/api/v1/media/media-1/workflow-inputs/input-2/content",
    }),
    reference({
      id: "input-3",
      status: "missing",
      original_node_id: "21",
      class_type: "LoadImage",
      source_filename: "missing.png",
      asset: null,
      content_url: null,
      last_error_code: "WORKFLOW_INPUT_NOT_FOUND",
      last_error_message: "ComfyUI no longer has this file.",
    }),
  ],
  total: 3,
  ready_count: 2,
  unresolved_count: 1,
};
