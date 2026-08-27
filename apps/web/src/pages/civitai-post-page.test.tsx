import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router";

import type { MediaDetail, WorkflowDetail } from "../lib/api";
import { CivitaiPostPage } from "./civitai-post-page";

const { apiRequestMock, copyTextMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  copyTextMock: vi.fn(),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../lib/api")>("../lib/api");
  return { ...actual, apiRequest: apiRequestMock };
});
vi.mock("../lib/clipboard", () => ({ copyText: copyTextMock }));

afterEach(() => {
  cleanup();
  apiRequestMock.mockReset();
  copyTextMock.mockReset();
});

function renderPage(entry = "/library/media-1/civitai-post?q=portrait") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes><Route path="/library/:mediaId/civitai-post" element={<CivitaiPostPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function setResponses(detail: MediaDetail = imageDetail, workflowData: WorkflowDetail = workflow) {
  apiRequestMock.mockImplementation((path: string) => {
    if (path === "/api/v1/media/media-1") return Promise.resolve(detail);
    if (path === "/api/v1/media/media-1/workflow?node_limit=1000&edge_limit=3000") return Promise.resolve(workflowData);
    throw new Error(`Unexpected request: ${path}`);
  });
}

describe("CivitaiPostPage", () => {
  it("uses only the two local record paths and prepares editable evidence", async () => {
    setResponses();
    renderPage();
    expect(await screen.findByDisplayValue("subject in soft light")).toBeInTheDocument();
    expect(apiRequestMock.mock.calls.map(([path]) => path)).toEqual([
      "/api/v1/media/media-1",
      "/api/v1/media/media-1/workflow?node_limit=1000&edge_limit=3000",
    ]);
    expect(screen.getByLabelText("Target")).toHaveValue("civitai_red");
    expect(screen.getByText("Workflow model usage")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to media" })).toHaveAttribute("href", "/library/media-1?q=portrait");
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Corrected title" } });
    expect(screen.getByText(/"title": "Corrected title"/)).toBeInTheDocument();
  });

  it("keeps target-specific draft status and payload synchronized", async () => {
    setResponses();
    renderPage();
    await screen.findByText("Post to Civitai");
    fireEvent.change(screen.getByLabelText("Target"), { target: { value: "civitai_com" } });
    expect(screen.getByText("civitai.com: Not connected / connectivity unverified")).toBeInTheDocument();
    expect(screen.getByText(/"target": "civitai_com"/)).toBeInTheDocument();
  });

  it("keeps publishing disabled and copies prepared JSON without a mutation", async () => {
    copyTextMock.mockResolvedValue(undefined);
    setResponses();
    renderPage();
    const publish = await screen.findByRole("button", { name: "Publishing not connected" });
    expect(publish).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Copy prepared JSON" }));
    await waitFor(() => expect(copyTextMock).toHaveBeenCalledTimes(1));
    expect(JSON.parse(copyTextMock.mock.calls[0][0])).toMatchObject({ media_id: "media-1", target: "civitai_red" });
    expect(await screen.findByText("Prepared JSON copied.")).toBeInTheDocument();
  });

  it("retains delimiters while editing and copies clean tags and checkpoints", async () => {
    copyTextMock.mockResolvedValue(undefined);
    setResponses();
    renderPage();
    const tags = await screen.findByLabelText("Tags (comma separated)");
    const checkpoints = screen.getByLabelText("Checkpoints (one per line)");
    fireEvent.change(tags, { target: { value: "first," } });
    expect(tags).toHaveValue("first,");
    fireEvent.change(tags, { target: { value: "first,second" } });
    fireEvent.change(checkpoints, { target: { value: "base\n" } });
    expect(checkpoints).toHaveValue("base\n");
    fireEvent.change(checkpoints, { target: { value: "base\nrefiner" } });
    fireEvent.click(screen.getByRole("button", { name: "Copy prepared JSON" }));
    await waitFor(() => expect(copyTextMock).toHaveBeenCalled());
    expect(JSON.parse(copyTextMock.mock.calls[0][0])).toMatchObject({
      post: { tags: ["first", "second"] },
      metadata: { checkpoints: ["base", "refiner"] },
    });
  });

  it("keeps LoRA name focus stable and updates the copied payload", async () => {
    copyTextMock.mockResolvedValue(undefined);
    setResponses(imageDetail, {
      ...workflow,
      model_usages: [...workflow.model_usages, { ...workflow.model_usages[0], id: "lora", observation_type: "lora_reference", raw_reference: "style.safetensors" }],
    });
    renderPage();
    const name = await screen.findByLabelText("LoRA 1 name");
    name.focus();
    fireEvent.change(name, { target: { value: "renamed style" } });
    expect(name).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Copy prepared JSON" }));
    await waitFor(() => expect(copyTextMock).toHaveBeenCalled());
    expect(JSON.parse(copyTextMock.mock.calls[0][0]).metadata.loras[0].name).toBe("renamed style");
  });

  it("explains video uncertainty and missing workflow evidence", async () => {
    setResponses({ ...imageDetail, kind: "video", original_filename: "clip.mov" }, { ...workflow, snapshot: null, observations: [], model_usages: [] });
    renderPage();
    expect(await screen.findByText(/does not prove video upload support/)).toBeInTheDocument();
    expect(screen.getByText(/No workflow snapshot is available/)).toBeInTheDocument();
    expect(screen.getAllByText("Missing evidence").length).toBeGreaterThan(0);
  });

  it("keeps an editable empty draft when workflow evidence fails", async () => {
    apiRequestMock.mockImplementation((path: string) => {
      if (path === "/api/v1/media/media-1") return Promise.resolve(imageDetail);
      if (path.includes("/workflow?")) return Promise.reject(new Error("workflow unavailable"));
      throw new Error(`Unexpected request: ${path}`);
    });
    renderPage();
    expect(await screen.findByText(/Workflow evidence could not be loaded/)).toBeInTheDocument();
    expect(screen.getByLabelText("Positive prompt")).toHaveValue("");
    expect(screen.getByLabelText("Title")).toHaveValue("portrait");
  });

  it("shows the media error boundary", async () => {
    apiRequestMock.mockRejectedValue(new Error("media unavailable"));
    renderPage();
    expect(await screen.findByText("The media record could not be loaded.")).toBeInTheDocument();
  });
});

const imageDetail: MediaDetail = {
  id: "media-1", kind: "image", status: "ready", detected_format: "png", mime_type: "image/png", width: 100, height: 100, duration_seconds: null, container: null, video_codec: null, warning_count: 0, byte_size: 10, original_filename: "portrait.png", workflow_status: "ready", evaluation_state: "not_started", is_trash: false, spatial_available: false, prefer_spatial_playback: false, spatial_view_preferred: false, favorite: false, file_created_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z", preview_url: "/preview", frame_rate: null, audio_codec: null, probe_data: {}, last_error_code: null, last_error_message: null, sha256: "sha", original_extension: ".png", updated_at: "2026-01-01T00:00:00Z", playback_url: "/playback", original_url: "/original", workflow_url: "/workflow", derivatives: [], variants: [], sources: [],
};

const workflow: WorkflowDetail = {
  media_id: "media-1", status: "ready", snapshot: { id: "snapshot-1", media_id: "media-1", reader_name: "reader", reader_version: "1", source_carrier: "metadata", evidence_sha256: "sha", api_prompt_status: "ready", visual_workflow_status: "missing", parse_status: "ready", issue_details: {}, error_code: null, error_message: null, graph_version: null, api_node_count: 0, visual_node_count: 0, edge_count: 0, created_at: "2026-01-01T00:00:00Z" }, nodes: [], edges: [], observations: [{ id: "positive", node_id: null, observation_type: "prompt", role: "positive", value: "subject in soft light", confidence: 1, correction_state: "inferred", evidence: {}, created_at: "2026-01-01T00:00:00Z" }], model_usages: [{ id: "checkpoint", node_id: "1", model_reference_id: "model", artifact_id: null, observation_type: "checkpoint_reference", raw_reference: "base.safetensors", artifact_display_name: "Base checkpoint", architecture_family: null, lineage: null, pipeline_pattern: "base", slot: "model", usage_order: 1, confidence: 1, correction_state: "inferred", evidence: {} }], runs: [], node_limit: 1000, node_offset: 0, nodes_truncated: false, edges_truncated: false, raw_url: null,
};
