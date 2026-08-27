import { describe, expect, it } from "vitest";

import type { SemanticObservation, WorkflowDetail, WorkflowModelUsage } from "./api";
import {
  civitaiTargetLabel,
  defaultCivitaiTarget,
  filenameTitle,
  loraStrength,
  prepareCivitaiPost,
  preparedPayload,
} from "./civitai-post";

const observation = (overrides: Partial<SemanticObservation>): SemanticObservation => ({
  id: "observation-1",
  node_id: null,
  observation_type: "prompt",
  role: "positive",
  value: "portrait in soft light",
  confidence: 1,
  correction_state: "inferred",
  evidence: {},
  created_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

const usage = (overrides: Partial<WorkflowModelUsage>): WorkflowModelUsage => ({
  id: "usage-1",
  node_id: "node-1",
  model_reference_id: "model-1",
  artifact_id: null,
  observation_type: "checkpoint_reference",
  raw_reference: "checkpoint.safetensors",
  artifact_display_name: null,
  architecture_family: null,
  lineage: null,
  pipeline_pattern: "unknown",
  slot: "model",
  usage_order: 1,
  confidence: 1,
  correction_state: "inferred",
  evidence: {},
  ...overrides,
});

const workflow = (overrides: Partial<WorkflowDetail> = {}): WorkflowDetail => ({
  media_id: "media-1",
  status: "ready",
  snapshot: null,
  nodes: [],
  edges: [],
  observations: [],
  model_usages: [],
  runs: [],
  node_limit: 1000,
  node_offset: 0,
  nodes_truncated: false,
  edges_truncated: false,
  raw_url: null,
  ...overrides,
});

describe("Civitai preparation", () => {
  it("uses the stable red target and a filename title", () => {
    expect(defaultCivitaiTarget).toBe("civitai_red");
    expect(civitaiTargetLabel("civitai_red")).toBe("civitai.red");
    expect(civitaiTargetLabel("civitai_com")).toBe("civitai.com");
    expect(filenameTitle("portrait.final.png")).toBe("portrait.final");
    expect(filenameTitle(".keep")).toBe(".keep");
  });

  it("orders prompt roles and prefers model usage over fallback observations", () => {
    const draft = prepareCivitaiPost({
      mediaId: "media-1",
      originalFilename: "portrait.png",
      workflow: workflow({
        observations: [
          observation({ id: "negative", role: "negative", value: "blur" }),
          observation({ id: "positive", role: "main", value: "subject" }),
          observation({
            id: "checkpoint-fallback",
            observation_type: "checkpoint_reference",
            value: "fallback.ckpt",
          }),
        ],
        model_usages: [usage({ artifact_display_name: "Resolved checkpoint" })],
      }),
    });
    expect(draft.metadata.positive_prompt).toBe("subject");
    expect(draft.metadata.negative_prompt).toBe("blur");
    expect(draft.metadata.checkpoints).toEqual(["Resolved checkpoint"]);
    expect(draft.evidence.checkpoints).toBe("model_usage");
  });

  it("falls back to observations and preserves unknown LoRA strength", () => {
    const draft = prepareCivitaiPost({
      mediaId: "media-1",
      originalFilename: "portrait.png",
      workflow: workflow({
        observations: [
          observation({
            observation_type: "lora_reference",
            value: "fallback-lora.safetensors",
            evidence: { strength: 0.45 },
          }),
        ],
      }),
    });
    expect(draft.metadata.loras).toEqual([
      { name: "fallback-lora.safetensors", strength: 0.45 },
    ]);
    expect(draft.evidence.loras).toBe("observation");
    expect(
      loraStrength(
        usage({ observation_type: "lora_reference", evidence: { strength: 0.8 } }),
        [],
      ),
    ).toBe(0.8);
  });

  it("uses an observation strength only when the usage lacks one, without mutation", () => {
    const usages = [
      usage({
        observation_type: "lora_reference",
        raw_reference: "style.safetensors",
        evidence: {},
      }),
    ];
    const observations = [
      observation({
        node_id: "node-1",
        observation_type: "lora_reference",
        value: "style.safetensors",
        evidence: { strength: "0.65" },
      }),
    ];
    const input = workflow({ model_usages: usages, observations });
    const before = structuredClone(input);
    const first = prepareCivitaiPost({ mediaId: "media-1", originalFilename: "x.png", workflow: input });
    const second = prepareCivitaiPost({ mediaId: "media-1", originalFilename: "x.png", workflow: input });
    expect(first).toEqual(second);
    expect(first.metadata.loras[0]?.strength).toBe("0.65");
    expect(input).toEqual(before);
  });

  it("keeps prepared output local and free of transport credentials or media addresses", () => {
    const payload = preparedPayload(
      prepareCivitaiPost({ mediaId: "media-1", originalFilename: "x.png" }),
    );
    const serialized = JSON.stringify(payload).toLocaleLowerCase();
    expect(serialized).not.toMatch(/url|token|authorization|bearer|uuid|upload/);
  });

  it("normalizes unfinished tag and checkpoint input only at the payload boundary", () => {
    const draft = prepareCivitaiPost({ mediaId: "media-1", originalFilename: "x.png" });
    draft.post.tags = ["first", "", " second "];
    draft.metadata.checkpoints = ["base", "", " refiner "];
    expect(preparedPayload(draft)).toMatchObject({
      post: { tags: ["first", "second"] },
      metadata: { checkpoints: ["base", "refiner"] },
    });
  });
});
