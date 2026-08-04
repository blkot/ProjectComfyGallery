import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkflowDetail, WorkflowSnapshot } from "../lib/api";
import { WorkflowInspector } from "./workflow-inspector";

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

describe("WorkflowInspector prompt copy", () => {
  it("copies the exact prompt from the Info panel and confirms success", async () => {
    apiRequestMock.mockResolvedValue(workflow);
    copyTextMock.mockResolvedValue(undefined);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <WorkflowInspector mediaId="media-1" />
      </QueryClientProvider>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Copy Positive" }));

    await waitFor(() => {
      expect(copyTextMock).toHaveBeenCalledWith("cinematic portrait\nsoft light");
      expect(
        screen.getByRole("button", { name: "Positive copied" }),
      ).toHaveTextContent("Copied");
    });
  });
});

const snapshot: WorkflowSnapshot = {
  id: "snapshot-1",
  media_id: "media-1",
  reader_name: "comfyui",
  reader_version: "1",
  source_carrier: "png",
  evidence_sha256: "evidence-sha",
  api_prompt_status: "ready",
  visual_workflow_status: "ready",
  parse_status: "ready",
  issue_details: {},
  error_code: null,
  error_message: null,
  graph_version: "1",
  api_node_count: 0,
  visual_node_count: 0,
  edge_count: 0,
  created_at: "2026-08-04T00:00:00Z",
};

const workflow: WorkflowDetail = {
  media_id: "media-1",
  status: "ready",
  snapshot,
  nodes: [],
  edges: [],
  observations: [
    {
      id: "prompt-1",
      node_id: null,
      observation_type: "prompt",
      role: "positive",
      value: "cinematic portrait\nsoft light",
      confidence: 1,
      correction_state: "original",
      evidence: {},
      created_at: "2026-08-04T00:00:00Z",
    },
  ],
  model_usages: [],
  runs: [],
  node_limit: 1000,
  node_offset: 0,
  nodes_truncated: false,
  edges_truncated: false,
  raw_url: null,
};
