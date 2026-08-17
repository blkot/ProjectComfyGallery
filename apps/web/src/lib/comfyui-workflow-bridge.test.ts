import { afterEach, describe, expect, it, vi } from "vitest";

import type { WorkflowRawEvidence } from "./api";
import {
  getComfyUiTarget,
  sendWorkflowToComfyUi,
  type ComfyUiTab,
} from "./comfyui-workflow-bridge";

afterEach(() => {
  vi.useRealTimers();
});

describe("ComfyUI workflow bridge", () => {
  it("prefers the configured visual workflow representation", async () => {
    const targetWindow = {
      closed: false,
      postMessage: vi.fn(),
    } as unknown as Window;
    const tab: ComfyUiTab = {
      window: targetWindow,
      origin: "http://comfy.example.test",
    };
    const promise = sendWorkflowToComfyUi(tab, "media-1", evidence);
    const posted = (targetWindow.postMessage as ReturnType<typeof vi.fn>).mock
      .calls[0]?.[0] as { requestId: string; representation: string };

    expect(posted.representation).toBe("visual_workflow");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: tab.origin,
        source: targetWindow,
        data: {
          type: "comfy-gallery-open-workflow-ack",
          version: 1,
          requestId: posted.requestId,
          ok: true,
        },
      }),
    );

    await expect(promise).resolves.toBeUndefined();
  });

  it("falls back to the API prompt when visual workflow is absent", async () => {
    const targetWindow = {
      closed: false,
      postMessage: vi.fn(),
    } as unknown as Window;
    const tab: ComfyUiTab = {
      window: targetWindow,
      origin: "http://comfy.example.test",
    };
    const promise = sendWorkflowToComfyUi(tab, "media-1", {
      ...evidence,
      visual_workflow: null,
    });
    const posted = (targetWindow.postMessage as ReturnType<typeof vi.fn>).mock
      .calls[0]?.[0] as { representation: string };

    expect(posted.representation).toBe("api_prompt");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: tab.origin,
        source: targetWindow,
        data: {
          type: "comfy-gallery-open-workflow-ack",
          version: 1,
          requestId: (targetWindow.postMessage as ReturnType<typeof vi.fn>).mock
            .calls[0]?.[0].requestId,
          ok: true,
        },
      }),
    );

    await expect(promise).resolves.toBeUndefined();
  });

  it("rejects when the ComfyUI tab does not acknowledge", async () => {
    vi.useFakeTimers();
    const targetWindow = {
      closed: false,
      postMessage: vi.fn(),
    } as unknown as Window;
    const promise = sendWorkflowToComfyUi(
      {
        window: targetWindow,
        origin: "http://comfy.example.test",
      },
      "media-1",
      evidence,
    );
    const rejection = expect(promise).rejects.toThrow("bridge extension");

    await vi.advanceTimersByTimeAsync(3_500);
    await rejection;
  });

  it("uses the current host with ComfyUI's default port when unset", () => {
    const currentUrl = new URL(window.location.href);
    const target = getComfyUiTarget("");
    expect(target.origin).toBe(`${currentUrl.protocol}//${currentUrl.hostname}:8188`);
    expect(target.href).toBe(`${target.origin}/`);
  });

  it("uses an explicitly configured ComfyUI URL", () => {
    expect(getComfyUiTarget("http://192.168.50.88:8188/")).toEqual({
      href: "http://192.168.50.88:8188/",
      origin: "http://192.168.50.88:8188",
    });
  });
});

const evidence: WorkflowRawEvidence = {
  snapshot_id: "snapshot-1",
  evidence_sha256: "sha",
  raw_metadata: {},
  raw_api_prompt_text: null,
  raw_visual_workflow_text: null,
  api_prompt: { "1": { class_type: "LoadImage", inputs: {} } },
  visual_workflow: { nodes: [], links: [] },
};
