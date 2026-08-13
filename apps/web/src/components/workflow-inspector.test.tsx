import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  WorkflowDetail,
  WorkflowModelUsage,
  WorkflowSnapshot,
} from "../lib/api";
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

describe("WorkflowInspector LoRA evidence", () => {
  it("shows the LoRA strength from its matching workflow observation", async () => {
    apiRequestMock.mockResolvedValue(workflowWithLora);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <WorkflowInspector mediaId="media-1" />
      </QueryClientProvider>,
    );

    const loraName = await screen.findByText("style.safetensors");
    expect(loraName.parentElement).toHaveTextContent("Strength 0.75");
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

const loraUsage: WorkflowModelUsage = {
  id: "usage-1",
  node_id: "node-1",
  model_reference_id: "reference-1",
  artifact_id: null,
  observation_type: "lora_reference",
  raw_reference: "style.safetensors",
  artifact_display_name: null,
  architecture_family: null,
  lineage: null,
  pipeline_pattern: "adapter_only_or_unresolved",
  slot: "adapter",
  usage_order: 0,
  confidence: 0.9,
  correction_state: "uncorrected",
  evidence: {},
};

const workflowWithLora: WorkflowDetail = {
  ...workflow,
  observations: [
    ...workflow.observations,
    {
      id: "lora-1",
      node_id: "node-1",
      observation_type: "lora_reference",
      role: "unclassified",
      value: "style.safetensors",
      confidence: 0.99,
      correction_state: "original",
      evidence: { strength: 0.75, clip_strength: 0.5 },
      created_at: "2026-08-04T00:00:00Z",
    },
  ],
  model_usages: [loraUsage],
};
